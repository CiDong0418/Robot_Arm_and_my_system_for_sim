#!/usr/bin/env python3
"""
head_xyz_detection.py
=====================
ROS 節點：頭部相機物體 XYZ + 半徑 R 偵測服務。

職責：
    - 訂閱 ROS Topic 獲取即時畫面與對齊的深度圖（不再獨佔 USB 硬體）
    - 自動獲取相機內參 (CameraInfo)
    - 持續顯示即時畫面（背景執行緒）
    - 訂閱 /head_detection/target 觸發 GroundingDINO 推論
    - 發布 3D 結果到 /head_detection/xyz 等頻道（單位：mm）
"""
import os
import sys
import time
import threading
import yaml

import cv2
import numpy as np
import rospy
import message_filters
from std_msgs.msg import String, Float32
from geometry_msgs.msg import PointStamped
from sensor_msgs.msg import Image, CameraInfo
from cv_bridge import CvBridge, CvBridgeError

_PKG_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SRC_DIR  = os.path.join(_PKG_DIR, "src")
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)

from depth_geometry           import (get_median_depth_in_box,
                                      compute_object_radius_3d,
                                      get_surface_xyz)

try:
    from grounding_dino_detector import GroundingDINODetector
    _GROUNDING_IMPORT_ERROR = None
except Exception as exc:
    GroundingDINODetector = None
    _GROUNDING_IMPORT_ERROR = exc

BBOX_DISPLAY_SEC = 10.0

_DEFAULT_CONFIG = {
    "grounding_dino": {
        "config":  "/opt/GroundingDINO/groundingdino/config/GroundingDINO_SwinB_cfg.py",
        "weights": "/opt/GroundingDINO/weights/groundingdino_swinb_cogcoor.pth",
        "device":  "auto",
    },
    "detection": {
        "box_threshold":  0.30,
        "text_threshold": 0.25,
        "max_attempts":   10,
    }
}

def _load_config(yaml_path: str) -> dict:
    if not os.path.isfile(yaml_path):
        return _DEFAULT_CONFIG
    with open(yaml_path, "r") as f:
        cfg = yaml.safe_load(f) or {}

    # 相容舊版 key：model -> grounding_dino
    if "grounding_dino" not in cfg and "model" in cfg:
        model_cfg = cfg.get("model", {})
        cfg["grounding_dino"] = {
            "config": model_cfg.get("config", _DEFAULT_CONFIG["grounding_dino"]["config"]),
            "weights": model_cfg.get("weights", _DEFAULT_CONFIG["grounding_dino"]["weights"]),
            "device": model_cfg.get("device", _DEFAULT_CONFIG["grounding_dino"]["device"]),
        }

    for section, defaults in _DEFAULT_CONFIG.items():
        cfg.setdefault(section, {})
        for k, v in defaults.items():
            cfg[section].setdefault(k, v)
    return cfg

def _draw_bbox(frame: np.ndarray, x1: int, y1: int, x2: int, y2: int,
               phrase: str, confidence: float, xyz_mm: tuple, radius_mm: float,
               center_px: tuple = None) -> None:
    GREEN, ORANGE, font, fs = (0, 255, 0), (0, 200, 255), cv2.FONT_HERSHEY_SIMPLEX, 0.55
    cv2.rectangle(frame, (x1, y1), (x2, y2), GREEN, 2)

    if center_px is not None:
        cx, cy = int(center_px[0]), int(center_px[1])
        RED = (0, 0, 255)
        cv2.circle(frame, (cx, cy), 6, RED, 2)
        cv2.drawMarker(frame, (cx, cy), RED, markerType=cv2.MARKER_CROSS, markerSize=16, thickness=2)
        cv2.putText(frame, f"P({cx},{cy})", (cx + 8, cy - 8), font, 0.5, RED, 1, cv2.LINE_AA)
    
    label = f"{phrase} {confidence:.2f} | X:{xyz_mm[0]:.3f}mm Y:{xyz_mm[1]:.3f}mm Z:{xyz_mm[2]:.3f}mm"
    (tw, th), _ = cv2.getTextSize(label, font, fs, 1)
    cv2.rectangle(frame, (x1, y1 - th - 8), (x1 + tw + 4, y1), GREEN, -1)
    cv2.putText(frame, label, (x1 + 2, y1 - 4), font, fs, (0, 0, 0), 1, cv2.LINE_AA)

    r_label = f"R = {radius_mm:.1f} mm"
    (rw, rh), _ = cv2.getTextSize(r_label, font, fs, 1)
    cv2.rectangle(frame, (x1, y2), (x1 + rw + 4, y2 + rh + 8), ORANGE, -1)
    cv2.putText(frame, r_label, (x1 + 2, y2 + rh + 2), font, fs, (0, 0, 0), 1, cv2.LINE_AA)

class HeadXYZDetectionNode:
    def __init__(self):
        rospy.init_node("head_xyz_detection", anonymous=False)
        cfg = _load_config(os.path.join(_PKG_DIR, "config.yaml"))
        
        self._box_thresh   = cfg["detection"]["box_threshold"]
        self._text_thresh  = cfg["detection"]["text_threshold"]
        self._max_attempts = cfg["detection"]["max_attempts"]
        self._has_display  = bool(os.environ.get("DISPLAY", ""))
        self.bridge = CvBridge()
        
        self._latest_color, self._latest_depth = None, None
        self._intrinsics_dict = None  # 改用純 Python 字典儲存相機內參
        self._depth_scale = 0.001     # D400 系列對齊後深度單位預設為 1mm = 0.001m
        self._camera_frame_id = "head_camera_color_optical_frame"

        dino_cfg = cfg["grounding_dino"]
        dino_config_path = dino_cfg["config"]
        dino_weights_path = dino_cfg["weights"]
        dino_device = dino_cfg.get("device", "auto")
        if isinstance(dino_device, str):
            dino_device = dino_device.strip().lower()
            if dino_device in ("", "auto", "none"):
                dino_device = None

        if not os.path.isfile(dino_config_path):
            raise FileNotFoundError(f"[head_xyz] GroundingDINO config 不存在: {dino_config_path}")
        if not os.path.isfile(dino_weights_path):
            raise FileNotFoundError(f"[head_xyz] GroundingDINO weights 不存在: {dino_weights_path}")
        if GroundingDINODetector is None:
            raise RuntimeError(
                f"[head_xyz] 無法載入 GroundingDINO 依賴：{_GROUNDING_IMPORT_ERROR}。"
                "請先安裝 torch 與 groundingdino。"
            )

        rospy.loginfo("[head_xyz] 載入 GroundingDINO 模型...")
        self._detector = GroundingDINODetector(
            config_path=dino_config_path,
            weights_path=dino_weights_path,
            device=dino_device,
        )

        self._last_detection, self._detection_lock = None, threading.Lock()
        self._current_target, self._target_lock = None, threading.Lock()

        # 發布與訂閱
        self._pub_xyz    = rospy.Publisher("/head_detection/xyz", PointStamped, queue_size=1)
        self._pub_radius = rospy.Publisher("/head_detection/radius", Float32, queue_size=1)
        self._pub_status = rospy.Publisher("/head_detection/status", String, queue_size=1)
        
        rospy.Subscriber("/head_detection/target", String, self._on_target_received, queue_size=1)
        rospy.Subscriber("/head_camera/color/camera_info", CameraInfo, self._camera_info_callback)

        # 時間同步影像流
        color_sub = message_filters.Subscriber('/head_camera/color/image_raw', Image)
        depth_sub = message_filters.Subscriber('/head_camera/aligned_depth_to_color/image_raw', Image)
        self.ts = message_filters.ApproximateTimeSynchronizer([color_sub, depth_sub], queue_size=10, slop=0.1)
        self.ts.registerCallback(self._sync_image_callback)

        if self._has_display:
            threading.Thread(target=self._display_loop, daemon=True).start()

        rospy.loginfo("[head_xyz] 系統就緒，等待相機畫面與辨識指令。")

    def _camera_info_callback(self, msg: CameraInfo):
        """將 ROS CameraInfo 轉換為純 Python 字典，徹底解耦 pyrealsense2"""
        if self._intrinsics_dict is None:
            self._intrinsics_dict = {
                'fx': msg.K[0], 'fy': msg.K[4],
                'ppx': msg.K[2], 'ppy': msg.K[5]
            }

    def _sync_image_callback(self, color_msg, depth_msg):
        try:
            color_image = self.bridge.imgmsg_to_cv2(color_msg, "bgr8")
            depth_image = self.bridge.imgmsg_to_cv2(depth_msg, "16UC1")

            if color_msg.header.frame_id:
                self._camera_frame_id = color_msg.header.frame_id
            
            self._latest_color, self._latest_depth = color_image, depth_image

            with self._target_lock:
                target = self._current_target
                self._current_target = None 
            if target:
                self._run_detection(target, color_image, depth_image)
        except CvBridgeError as e:
            rospy.logerr(f"CV Bridge Error: {e}")

    def _run_detection(self, target: str, color_image, depth_image):
        if self._intrinsics_dict is None:
            rospy.logwarn("[head_xyz] 尚未收到 CameraInfo，無法計算。")
            return

        detections = self._detector.detect(
            color_image, target, 
            box_threshold=self._box_thresh, text_threshold=self._text_thresh
        )

        if not detections:
            self._publish_status(f"FAIL | 未偵測到 {target}")
            return

        best = max(detections, key=lambda d: d["confidence"])
        x1, y1, x2, y2 = best["bbox"]

        depth_median = get_median_depth_in_box(depth_image, x1, y1, x2, y2, self._depth_scale)
        if depth_median is None: return

        # 餵入純字典內參進行數學運算
        xyz = get_surface_xyz(self._intrinsics_dict, x1, y1, x2, y2, depth_median)
        R   = compute_object_radius_3d(self._intrinsics_dict, x1, y1, x2, y2, depth_median)
        center_px = ((x1 + x2) // 2, (y1 + y2) // 2)
        xyz_mm = (xyz[0] * 1000, xyz[1] * 1000, xyz[2] * 1000)
        R_mm   = R * 1000
        with self._detection_lock:
            self._last_detection = {
                "bbox": (x1, y1, x2, y2), "phrase": best["phrase"], 
                "confidence": best["confidence"], "xyz_mm": xyz_mm, "R_mm": R_mm,
                "center_px": center_px,
                "expire_at": time.time() + BBOX_DISPLAY_SEC
            }

        self._publish_xyz(xyz_mm)
        self._publish_radius(R_mm)
        self._publish_status(f"OK | target={target} XYZ=({xyz_mm[0]:.3f}, {xyz_mm[1]:.3f}, {xyz_mm[2]:.3f})mm R={R_mm:.1f}mm")

    def _display_loop(self) -> None:
        win = "Head Detection | press q to close"
        cv2.namedWindow(win, cv2.WINDOW_NORMAL)
        while not rospy.is_shutdown():
            if self._latest_color is None:
                time.sleep(0.03); continue
            
            display = self._latest_color.copy()
            with self._detection_lock:
                det = self._last_detection
                if det and time.time() < det["expire_at"]:
                    _draw_bbox(display, *det["bbox"], det["phrase"], det["confidence"], det["xyz_mm"], det["R_mm"], det.get("center_px"))
                elif det and time.time() >= det["expire_at"]:
                    self._last_detection = None

            cv2.imshow(win, display)
            if cv2.waitKey(1) & 0xFF == ord('q'): break
            time.sleep(0.03)
        cv2.destroyAllWindows()

    def _on_target_received(self, msg: String) -> None:
        with self._target_lock: self._current_target = msg.data.strip()

    def _publish_xyz(self, xyz: tuple, frame_id: str = None) -> None:
        msg = PointStamped()
        msg.header.stamp = rospy.Time.now()
        msg.header.frame_id = frame_id if frame_id else self._camera_frame_id
        msg.point.x, msg.point.y, msg.point.z = xyz
        self._pub_xyz.publish(msg)

    def _publish_radius(self, r: float) -> None: self._pub_radius.publish(Float32(data=float(r)))
    def _publish_status(self, text: str) -> None: self._pub_status.publish(String(data=text))
    def shutdown(self) -> None: cv2.destroyAllWindows()

if __name__ == "__main__":
    node = HeadXYZDetectionNode()
    rospy.on_shutdown(node.shutdown)
    rospy.spin()