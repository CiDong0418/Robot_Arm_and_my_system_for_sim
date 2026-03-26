#!/usr/bin/env python3
"""
aruco_id.py
===========
ROS 節點：依照觸發目標相機（例如 head）偵測 ArUco，回傳 ID 與相機座標 XYZ。

功能：
    - 訂閱觸發 Topic：/aruco_detection/target（String）
      例：發送 "head"
    - 讀取對應相機彩色 + 對齊深度 + CameraInfo
    - 偵測 ArUco Marker
    - 發布結果到 /aruco_detection/result（String, JSON）
    - 發布狀態到 /aruco_detection/status（String）
"""

import json
import os
import threading
import time

import cv2
import numpy as np
import rospy
import message_filters
from cv_bridge import CvBridge, CvBridgeError
from sensor_msgs.msg import Image, CameraInfo
from std_msgs.msg import String


DEPTH_MIN_M = 0.1
DEPTH_MAX_M = 5.0
DISPLAY_HOLD_SEC = 6.0


class ArucoIDNode:
    def __init__(self):
        rospy.init_node("aruco_id_node", anonymous=False)

        if not hasattr(cv2, "aruco"):
            raise RuntimeError("[aruco_id] 目前 OpenCV 沒有 aruco 模組，請安裝 opencv-contrib-python")

        self._bridge = CvBridge()
        self._lock = threading.Lock()
        self._pending_target = None

        self._depth_scale = rospy.get_param("~depth_scale", 0.001)
        self._aruco_dict_name = rospy.get_param("~aruco_dict", "DICT_5X5_50")
        self._marker_size_mm = float(rospy.get_param("~marker_size_mm", 50.0))
        self._depth_window_half = int(rospy.get_param("~depth_window_half", 3))
        self._show_window = bool(rospy.get_param("~show_window", bool(os.environ.get("DISPLAY", ""))))

        self._camera_cfg = {
            "head": {
                "color": "/head_camera/color/image_raw",
                "depth": "/head_camera/aligned_depth_to_color/image_raw",
                "camera_info": "/head_camera/color/camera_info",
                "default_frame_id": "head_camera_color_optical_frame",
            }
        }

        self._intrinsics = {}
        self._frame_id = {
            key: cfg["default_frame_id"] for key, cfg in self._camera_cfg.items()
        }
        self._latest_frame = {key: None for key in self._camera_cfg.keys()}
        self._last_overlay = {key: None for key in self._camera_cfg.keys()}

        self._pub_result = rospy.Publisher("/aruco_detection/result", String, queue_size=10)
        self._pub_status = rospy.Publisher("/aruco_detection/status", String, queue_size=10)

        rospy.Subscriber("/aruco_detection/target", String, self._on_target, queue_size=10)

        self._sync_handles = []
        for cam_key, cfg in self._camera_cfg.items():
            rospy.Subscriber(cfg["camera_info"], CameraInfo, self._camera_info_cb, callback_args=cam_key, queue_size=1)

            color_sub = message_filters.Subscriber(cfg["color"], Image)
            depth_sub = message_filters.Subscriber(cfg["depth"], Image)
            ts = message_filters.ApproximateTimeSynchronizer([color_sub, depth_sub], queue_size=10, slop=0.1)
            ts.registerCallback(self._sync_image_cb, cam_key)
            self._sync_handles.append((color_sub, depth_sub, ts))

        self._aruco_dict = self._create_aruco_dict(self._aruco_dict_name)
        self._aruco_detector = self._create_aruco_detector()

        if self._show_window:
            threading.Thread(target=self._display_loop, daemon=True).start()

        rospy.loginfo(
            f"[aruco_id] 就緒，等待 /aruco_detection/target（例如：head），"
            f"aruco_dict={self._aruco_dict_name} marker_size_mm={self._marker_size_mm:.1f} show_window={self._show_window}"
        )

    def _create_aruco_dict(self, dict_name: str):
        if not hasattr(cv2.aruco, dict_name):
            rospy.logwarn(f"[aruco_id] 找不到字典 {dict_name}，改用 DICT_4X4_50")
            dict_name = "DICT_4X4_50"
        return cv2.aruco.getPredefinedDictionary(getattr(cv2.aruco, dict_name))

    def _create_aruco_detector(self):
        if hasattr(cv2.aruco, "DetectorParameters") and hasattr(cv2.aruco, "ArucoDetector"):
            params = cv2.aruco.DetectorParameters()
            return cv2.aruco.ArucoDetector(self._aruco_dict, params)
        params = cv2.aruco.DetectorParameters_create()
        return (self._aruco_dict, params)

    def _detect_markers(self, gray: np.ndarray):
        if isinstance(self._aruco_detector, tuple):
            dct, params = self._aruco_detector
            corners, ids, _ = cv2.aruco.detectMarkers(gray, dct, parameters=params)
            return corners, ids
        corners, ids, _ = self._aruco_detector.detectMarkers(gray)
        return corners, ids

    def _camera_info_cb(self, msg: CameraInfo, cam_key: str):
        if cam_key not in self._intrinsics:
            self._intrinsics[cam_key] = {
                "fx": msg.K[0],
                "fy": msg.K[4],
                "ppx": msg.K[2],
                "ppy": msg.K[5],
            }

    def _on_target(self, msg: String):
        target = msg.data.strip().lower()
        if target not in self._camera_cfg:
            self._publish_status(f"FAIL | 不支援 target={target}，目前僅支援: {','.join(self._camera_cfg.keys())}")
            return

        with self._lock:
            self._pending_target = target
        self._publish_status(f"TRIGGER | target={target}")

    def _sync_image_cb(self, color_msg: Image, depth_msg: Image, cam_key: str):
        try:
            color_image = self._bridge.imgmsg_to_cv2(color_msg, "bgr8")
            depth_image = self._bridge.imgmsg_to_cv2(depth_msg, "16UC1")
        except CvBridgeError as exc:
            rospy.logerr(f"[aruco_id] CvBridgeError: {exc}")
            return

        if color_msg.header.frame_id:
            self._frame_id[cam_key] = color_msg.header.frame_id

        self._latest_frame[cam_key] = color_image

        with self._lock:
            should_run = self._pending_target == cam_key
            if should_run:
                self._pending_target = None

        if should_run:
            self._run_detection(cam_key, color_image, depth_image)

    def _run_detection(self, cam_key: str, color_image: np.ndarray, depth_image: np.ndarray):
        intr = self._intrinsics.get(cam_key)
        if intr is None:
            self._publish_status(f"FAIL | {cam_key} 尚未收到 CameraInfo")
            return

        gray = cv2.cvtColor(color_image, cv2.COLOR_BGR2GRAY)
        corners, ids = self._detect_markers(gray)
        vis = color_image.copy()

        if ids is None or len(ids) == 0:
            self._last_overlay[cam_key] = {
                "frame": vis,
                "expire_at": time.time() + DISPLAY_HOLD_SEC,
            }
            self._publish_status(f"FAIL | target={cam_key} 未偵測到 ArUco")
            self._pub_result.publish(String(data=json.dumps({
                "target": cam_key,
                "frame_id": self._frame_id.get(cam_key, ""),
                "markers": [],
                "count": 0,
            }, ensure_ascii=False)))
            return

        markers = []
        for marker_id, marker_corners in zip(ids.flatten().tolist(), corners):
            pts = marker_corners.reshape(-1, 2)
            u = float(np.mean(pts[:, 0]))
            v = float(np.mean(pts[:, 1]))

            int_pts = pts.astype(np.int32)
            cv2.polylines(vis, [int_pts], True, (0, 255, 0), 2)
            cv2.circle(vis, (int(round(u)), int(round(v))), 5, (0, 0, 255), -1)

            depth_m = self._median_depth_at(depth_image, u, v)
            if depth_m is None:
                cv2.putText(
                    vis,
                    f"ID:{int(marker_id)} no-depth",
                    (int(round(u)) + 8, int(round(v)) - 8),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (0, 0, 255),
                    1,
                    cv2.LINE_AA,
                )
                continue

            x, y, z = self._pixel_to_xyz(intr, u, v, depth_m)
            cv2.putText(
                vis,
                f"ID:{int(marker_id)} X:{x*1000:.1f} Y:{y*1000:.1f} Z:{z*1000:.1f}mm",
                (int(round(u)) + 8, int(round(v)) - 8),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0, 255, 255),
                1,
                cv2.LINE_AA,
            )
            markers.append({
                "id": int(marker_id),
                "xyz_mm": {
                    "x": x * 1000.0,
                    "y": y * 1000.0,
                    "z": z * 1000.0,
                },
                "pixel": {
                    "u": u,
                    "v": v,
                }
            })

        self._last_overlay[cam_key] = {
            "frame": vis,
            "expire_at": time.time() + DISPLAY_HOLD_SEC,
        }

        result = {
            "target": cam_key,
            "frame_id": self._frame_id.get(cam_key, ""),
            "marker_size_mm": self._marker_size_mm,
            "count": len(markers),
            "markers": markers,
            "stamp": rospy.Time.now().to_sec(),
        }
        self._pub_result.publish(String(data=json.dumps(result, ensure_ascii=False)))

        if markers:
            ids_text = ",".join(str(m["id"]) for m in markers)
            self._publish_status(f"OK | target={cam_key} markers={len(markers)} ids=[{ids_text}]")
        else:
            self._publish_status(f"FAIL | target={cam_key} ArUco 有偵測到但無有效深度")

    def _median_depth_at(self, depth_image: np.ndarray, u: float, v: float):
        h, w = depth_image.shape[:2]
        cx, cy = int(round(u)), int(round(v))
        half = max(1, self._depth_window_half)

        x1 = max(0, cx - half)
        x2 = min(w, cx + half + 1)
        y1 = max(0, cy - half)
        y2 = min(h, cy + half + 1)

        roi = depth_image[y1:y2, x1:x2].astype(np.float32) * self._depth_scale
        valid = roi[(roi > DEPTH_MIN_M) & (roi < DEPTH_MAX_M)]
        if valid.size == 0:
            return None
        return float(np.median(valid))

    @staticmethod
    def _pixel_to_xyz(intr: dict, u: float, v: float, depth_m: float):
        fx, fy = intr["fx"], intr["fy"]
        ppx, ppy = intr["ppx"], intr["ppy"]
        x = (u - ppx) / fx * depth_m
        y = (v - ppy) / fy * depth_m
        z = depth_m
        return x, y, z

    def _publish_status(self, text: str):
        self._pub_status.publish(String(data=text))

    def _display_loop(self):
        win = "ArUco Detection"
        cv2.namedWindow(win, cv2.WINDOW_NORMAL)
        while not rospy.is_shutdown():
            display = None
            for cam_key in self._camera_cfg.keys():
                overlay = self._last_overlay.get(cam_key)
                if overlay and time.time() < overlay["expire_at"]:
                    display = overlay["frame"]
                else:
                    frame = self._latest_frame.get(cam_key)
                    if frame is not None:
                        display = frame.copy()
                        cv2.putText(
                            display,
                            f"camera={cam_key} (waiting trigger)",
                            (15, 25),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.7,
                            (255, 255, 255),
                            2,
                            cv2.LINE_AA,
                        )

                if display is not None:
                    break

            if display is not None:
                cv2.imshow(win, display)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
            time.sleep(0.03)

        cv2.destroyAllWindows()


if __name__ == "__main__":
    node = ArucoIDNode()
    rospy.spin()
