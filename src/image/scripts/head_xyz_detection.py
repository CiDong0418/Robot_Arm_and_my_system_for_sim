#!/usr/bin/env python3
"""
head_xyz_detection.py
=====================
ROS 節點：頭部相機物體 XYZ + 半徑 R 偵測服務。

職責：
    - 相機啟動後即持續顯示即時畫面（背景執行緒）
    - 訂閱 /head_detection/target，收到物品名稱後執行偵測
    - 偵測成功：在畫面上顯示 BBox 停留 BBOX_DISPLAY_SEC 秒後消失
    - 發布結果到 /head_detection/xyz、/head_detection/radius、/head_detection/status

訂閱:
    /head_detection/target  (std_msgs/String)  — 要辨識的物品名稱

發布:
    /head_detection/xyz     (geometry_msgs/PointStamped)
    /head_detection/radius  (std_msgs/Float32)
    /head_detection/status  (std_msgs/String)
"""
import os
import sys
import time
import threading
import yaml

import cv2
import numpy as np
import rospy
from std_msgs.msg import String, Float32
from geometry_msgs.msg import PointStamped

# ── src/ 模組路徑 ──
_PKG_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SRC_DIR  = os.path.join(_PKG_DIR, "src")
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)

from realsense_stream         import RealSenseStream
from grounding_dino_detector  import GroundingDINODetector
from depth_geometry           import (get_median_depth_in_box,
                                      compute_object_radius_3d,
                                      get_surface_xyz)

# ── 常數 ──
BBOX_DISPLAY_SEC = 3.0      # BBox 在畫面上顯示幾秒

# ──────────────────────────── 預設設定 ────────────────────────────────────
_DEFAULT_CONFIG = {
    "grounding_dino": {
        "config":  "/opt/GroundingDINO/groundingdino/config/GroundingDINO_SwinB_cfg.py",
        "weights": "/opt/GroundingDINO/weights/groundingdino_swinb_cogcoor.pth",
    },
    "detection": {
        "box_threshold":  0.30,
        "text_threshold": 0.25,
        "max_attempts":   10,
    },
    "camera": {
        "color_width":  1280,
        "color_height": 720,
        "depth_width":  1280,
        "depth_height": 720,
        "fps":          30,
        "warmup_frames": 30,
    },
}


def _load_config(yaml_path: str) -> dict:
    """讀取 config.yaml，不存在時使用預設值。"""
    if not os.path.isfile(yaml_path):
        rospy.logwarn(f"[head_xyz] 找不到 config.yaml（{yaml_path}），使用預設值。")
        return _DEFAULT_CONFIG
    with open(yaml_path, "r") as f:
        cfg = yaml.safe_load(f) or {}
    for section, defaults in _DEFAULT_CONFIG.items():
        cfg.setdefault(section, {})
        for k, v in defaults.items():
            cfg[section].setdefault(k, v)
    return cfg


# ──────────────────────────── 視覺化輔助 ──────────────────────────────────
def _draw_bbox(frame: np.ndarray,
               x1: int, y1: int, x2: int, y2: int,
               phrase: str, confidence: float,
               xyz: tuple, radius_m: float) -> None:
    """在影像上繪製 BBox、XYZ 標注（上方）與半徑 R 標注（下方）。"""
    GREEN  = (0, 255, 0)
    ORANGE = (0, 200, 255)
    font   = cv2.FONT_HERSHEY_SIMPLEX
    fs     = 0.55

    cv2.rectangle(frame, (x1, y1), (x2, y2), GREEN, 2)

    # 上方：物品名稱 + XYZ
    label = (f"{phrase} {confidence:.2f} | "
             f"X:{xyz[0]:.3f}m Y:{xyz[1]:.3f}m Z:{xyz[2]:.3f}m")
    (tw, th), _ = cv2.getTextSize(label, font, fs, 1)
    cv2.rectangle(frame, (x1, y1 - th - 8), (x1 + tw + 4, y1), GREEN, -1)
    cv2.putText(frame, label, (x1 + 2, y1 - 4),
                font, fs, (0, 0, 0), 1, cv2.LINE_AA)

    # 下方：半徑 R（橘黃色）
    r_label = f"R = {radius_m*100:.1f} cm"
    (rw, rh), _ = cv2.getTextSize(r_label, font, fs, 1)
    cv2.rectangle(frame, (x1, y2), (x1 + rw + 4, y2 + rh + 8), ORANGE, -1)
    cv2.putText(frame, r_label, (x1 + 2, y2 + rh + 2),
                font, fs, (0, 0, 0), 1, cv2.LINE_AA)


# ──────────────────────────── ROS 節點 ────────────────────────────────────
class HeadXYZDetectionNode:
    """頭部相機物體偵測 ROS 節點（含即時畫面顯示）。"""

    def __init__(self):
        rospy.init_node("head_xyz_detection", anonymous=False)

        yaml_path = os.path.join(_PKG_DIR, "config.yaml")
        cfg       = _load_config(yaml_path)

        det_cfg  = cfg["detection"]
        cam_cfg  = cfg["camera"]
        dino_cfg = cfg["grounding_dino"]

        self._box_thresh   = det_cfg["box_threshold"]
        self._text_thresh  = det_cfg["text_threshold"]
        self._max_attempts = det_cfg["max_attempts"]
        self._has_display  = bool(os.environ.get("DISPLAY", ""))

        # ── 初始化相機 ──
        rospy.loginfo("[head_xyz] 啟動 RealSense 相機...")
        self._camera = RealSenseStream(
            color_width   = cam_cfg["color_width"],
            color_height  = cam_cfg["color_height"],
            depth_width   = cam_cfg["depth_width"],
            depth_height  = cam_cfg["depth_height"],
            fps           = cam_cfg["fps"],
            warmup_frames = cam_cfg["warmup_frames"],
        )
        self._camera.start()
        rospy.loginfo("[head_xyz] 相機就緒。")

        # ── 初始化偵測器 ──
        rospy.loginfo("[head_xyz] 載入 GroundingDINO 模型...")
        self._detector = GroundingDINODetector(
            config_path  = dino_cfg["config"],
            weights_path = dino_cfg["weights"],
        )
        rospy.loginfo(f"[head_xyz] 模型就緒（device={self._detector.device}）。")

        # ── 上次偵測結果（供顯示執行緒使用）──
        # { 'bbox': (x1,y1,x2,y2), 'phrase': str, 'confidence': float,
        #   'xyz': tuple, 'R': float, 'expire_at': float (time.time()) }
        self._last_detection = None
        self._detection_lock = threading.Lock()

        # ── Publishers ──
        self._pub_xyz    = rospy.Publisher("/head_detection/xyz",    PointStamped, queue_size=1)
        self._pub_radius = rospy.Publisher("/head_detection/radius", Float32,       queue_size=1)
        self._pub_status = rospy.Publisher("/head_detection/status", String,        queue_size=1)

        # ── Subscriber ──
        rospy.Subscriber("/head_detection/target", String,
                         self._on_target_received, queue_size=1)

        # ── 啟動即時畫面顯示執行緒 ──
        if self._has_display:
            self._display_thread = threading.Thread(
                target=self._display_loop, daemon=True)
            self._display_thread.start()
            rospy.loginfo("[head_xyz] 即時畫面顯示已啟動（按 q 可關閉視窗）。")
        else:
            rospy.logwarn("[head_xyz] 未偵測到 DISPLAY，跳過視窗顯示。")

        rospy.loginfo("[head_xyz] 節點就緒，等待 /head_detection/target 訊息。")

    # ── 即時畫面顯示執行緒 ────────────────────────────────────────────────

    def _display_loop(self) -> None:
        """
        持續從相機取幀並顯示。
        若目前有偵測結果且尚未過期（< BBOX_DISPLAY_SEC 秒），則疊加 BBox；
        超過時間後自動清除，回到純畫面直到下次偵測。
        """
        win = "Head Detection | press q to close"
        cv2.namedWindow(win, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(win, 1280, 720)

        while not rospy.is_shutdown():
            frames = self._camera.get_aligned_frames()
            if frames is None:
                continue

            color_image, _, _, _, _ = frames
            display = color_image.copy()

            # 疊加 BBox（若在有效期內）
            with self._detection_lock:
                det = self._last_detection
                if det is not None and time.time() < det["expire_at"]:
                    x1, y1, x2, y2 = det["bbox"]
                    _draw_bbox(display,
                               x1, y1, x2, y2,
                               det["phrase"], det["confidence"],
                               det["xyz"],    det["R"])
                    # 顯示倒數秒數
                    remaining = det["expire_at"] - time.time()
                    cv2.putText(display,
                                f"BBox expires in {remaining:.1f}s",
                                (10, 90), cv2.FONT_HERSHEY_SIMPLEX,
                                0.7, (0, 255, 255), 2)
                elif det is not None and time.time() >= det["expire_at"]:
                    self._last_detection = None   # 過期清除

            # 固定左上角提示
            cv2.putText(display, "Waiting for detection target...",
                        (10, 30), cv2.FONT_HERSHEY_SIMPLEX,
                        0.7, (200, 200, 200), 2)

            try:
                cv2.imshow(win, display)
                key = cv2.waitKey(1) & 0xFF
                if key == ord('q'):
                    rospy.loginfo("[head_xyz] 使用者關閉顯示視窗。")
                    cv2.destroyAllWindows()
                    break
            except cv2.error:
                break

    # ── Callback ──────────────────────────────────────────────────────────

    def _on_target_received(self, msg: String) -> None:
        target = msg.data.strip()
        if not target:
            rospy.logwarn("[head_xyz] 收到空字串，忽略。")
            return

        rospy.loginfo(f"[head_xyz] 開始偵測目標：'{target}'")

        for attempt in range(1, self._max_attempts + 1):
            frames = self._camera.get_aligned_frames()
            if frames is None:
                rospy.logwarn(f"[head_xyz] 第 {attempt} 幀取得失敗，跳過。")
                continue

            color_image, depth_image, depth_frame, intrinsics, depth_scale = frames

            detections = self._detector.detect(
                color_image, target,
                box_threshold  = self._box_thresh,
                text_threshold = self._text_thresh,
            )

            if not detections:
                rospy.logdebug(f"[head_xyz] 第 {attempt} 幀未偵測到 '{target}'。")
                continue

            best = max(detections, key=lambda d: d["confidence"])
            x1, y1, x2, y2 = best["bbox"]

            depth_median = get_median_depth_in_box(
                depth_image, x1, y1, x2, y2, depth_scale)
            if depth_median is None:
                rospy.logwarn(f"[head_xyz] 第 {attempt} 幀深度無效，繼續嘗試。")
                continue

            xyz = get_surface_xyz(intrinsics, x1, y1, x2, y2, depth_median)
            R   = compute_object_radius_3d(intrinsics, x1, y1, x2, y2, depth_median)

            # ── 更新顯示用偵測結果（停留 BBOX_DISPLAY_SEC 秒）──
            with self._detection_lock:
                self._last_detection = {
                    "bbox":       (x1, y1, x2, y2),
                    "phrase":     best["phrase"],
                    "confidence": best["confidence"],
                    "xyz":        xyz,
                    "R":          R,
                    "expire_at":  time.time() + BBOX_DISPLAY_SEC,
                }

            # ── 發布 ROS 結果 ──
            self._publish_xyz(xyz, target)
            self._publish_radius(R)
            self._publish_status(
                f"OK | target={target} conf={best['confidence']:.3f} "
                f"X={xyz[0]:.3f}m Y={xyz[1]:.3f}m Z={xyz[2]:.3f}m "
                f"R={R*100:.1f}cm attempt={attempt}"
            )

            rospy.loginfo(
                f"[head_xyz] 偵測成功（第 {attempt} 幀）| "
                f"conf={best['confidence']:.3f} | "
                f"XYZ=({xyz[0]:.3f}, {xyz[1]:.3f}, {xyz[2]:.3f})m | "
                f"R={R*100:.1f}cm"
            )
            return

        fail_msg = f"FAIL | target='{target}' | 嘗試 {self._max_attempts} 幀均未偵測到目標"
        rospy.logwarn(f"[head_xyz] {fail_msg}")
        self._publish_status(fail_msg)

    # ── 發布輔助方法 ──────────────────────────────────────────────────────

    def _publish_xyz(self, xyz: tuple, frame_id: str = "camera_color_optical_frame") -> None:
        msg = PointStamped()
        msg.header.stamp    = rospy.Time.now()
        msg.header.frame_id = frame_id
        msg.point.x = xyz[0]
        msg.point.y = xyz[1]
        msg.point.z = xyz[2]
        self._pub_xyz.publish(msg)

    def _publish_radius(self, radius_m: float) -> None:
        msg = Float32()
        msg.data = float(radius_m)
        self._pub_radius.publish(msg)

    def _publish_status(self, text: str) -> None:
        msg = String()
        msg.data = text
        self._pub_status.publish(msg)

    # ── 清理 ──────────────────────────────────────────────────────────────

    def shutdown(self) -> None:
        rospy.loginfo("[head_xyz] 節點關閉，停止相機。")
        self._camera.stop()
        cv2.destroyAllWindows()


# ──────────────────────────── 程式入口 ────────────────────────────────────
if __name__ == "__main__":
    node = HeadXYZDetectionNode()
    rospy.on_shutdown(node.shutdown)
    rospy.spin()
