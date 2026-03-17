#!/usr/bin/env python3
"""
realsense_stream.py
===================
RealSense 相機串流管理模組。

職責（單一功能）：
    管理 RealSense 相機的生命週期（開啟、取幀、關閉），
    並將深度影像對齊至彩色影像後統一回傳。

此模組不依賴 ROS，也不做任何物件辨識或幾何計算。
"""
from typing import Optional, Tuple
import numpy as np
import pyrealsense2 as rs


class RealSenseStream:
    """
    RealSense RGBD 相機串流管理器。

    用法:
        stream = RealSenseStream()
        stream.start()
        color, depth_img, depth_frame, intrinsics, scale = stream.get_aligned_frames()
        stream.stop()
    """

    def __init__(self,
                 color_width:  int = 1280,
                 color_height: int = 720,
                 depth_width:  int = 1280,
                 depth_height: int = 720,
                 fps:          int = 30,
                 warmup_frames: int = 30):
        """
        參數:
            color_width/height : 彩色影像解析度
            depth_width/height : 深度影像解析度
            fps                : 串流幀率
            warmup_frames      : 暖機丟棄幀數（穩定曝光）
        """
        self._color_w  = color_width
        self._color_h  = color_height
        self._depth_w  = depth_width
        self._depth_h  = depth_height
        self._fps      = fps
        self._warmup   = warmup_frames

        self._pipeline   = rs.pipeline()
        self._align      = rs.align(rs.stream.color)
        self._depth_scale: Optional[float] = None
        self._intrinsics: Optional[rs.intrinsics] = None
        self._running    = False

    # ── 公開介面 ──────────────────────────────────────────────────────────

    def start(self) -> None:
        """啟動相機串流並執行暖機。"""
        cfg = rs.config()
        cfg.enable_stream(rs.stream.color,
                          self._color_w, self._color_h,
                          rs.format.bgr8, self._fps)
        cfg.enable_stream(rs.stream.depth,
                          self._depth_w, self._depth_h,
                          rs.format.z16, self._fps)

        profile = self._pipeline.start(cfg)

        # 深度比例（raw unit → 公尺）
        depth_sensor      = profile.get_device().first_depth_sensor()
        self._depth_scale = depth_sensor.get_depth_scale()

        # 彩色相機內參
        color_profile     = profile.get_stream(rs.stream.color)
        self._intrinsics  = color_profile.as_video_stream_profile().get_intrinsics()

        # 暖機
        for _ in range(self._warmup):
            self._pipeline.wait_for_frames()

        self._running = True

    def stop(self) -> None:
        """停止相機串流。"""
        if self._running:
            self._pipeline.stop()
            self._running = False

    def get_aligned_frames(self) -> Optional[Tuple[
            np.ndarray, np.ndarray, object, object, float]]:
        """
        取一幀對齊（深度對齊至彩色）影像。

        回傳 tuple:
            color_image  (np.ndarray, BGR HxWx3)
            depth_image  (np.ndarray, uint16 HxW)
            depth_frame  (rs.depth_frame)
            intrinsics   (rs.intrinsics，彩色相機)
            depth_scale  (float，m/unit)

        若任一幀無效則回傳 None。
        """
        if not self._running:
            return None

        frames         = self._pipeline.wait_for_frames()
        aligned        = self._align.process(frames)
        color_frame    = aligned.get_color_frame()
        depth_frame    = aligned.get_depth_frame()

        if not color_frame or not depth_frame:
            return None

        color_image = np.asanyarray(color_frame.get_data())
        depth_image = np.asanyarray(depth_frame.get_data())

        return (color_image, depth_image,
                depth_frame, self._intrinsics, self._depth_scale)

    # ── 屬性（唯讀） ───────────────────────────────────────────────────────

    @property
    def intrinsics(self) -> Optional[object]:
        """彩色相機內參（start() 之後才有值）。"""
        return self._intrinsics

    @property
    def depth_scale(self) -> Optional[float]:
        """深度比例（start() 之後才有值）。"""
        return self._depth_scale

    @property
    def is_running(self) -> bool:
        return self._running

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *_):
        self.stop()
