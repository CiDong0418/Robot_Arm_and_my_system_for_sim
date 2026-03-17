#!/usr/bin/env python3
"""
realsense_stream.py
===================
RealSense 相機串流管理模組。

⚠️ 【重要架構改動備註】 ⚠️
在多機 ROS 架構（multi_camera.launch）下，此模組已正式「停用」。
因為 ROS 節點已經接管了 USB 的獨佔權。此程式保留僅作為「繞過 ROS 的單機硬體裸測與除錯工具」。
"""
from typing import Optional, Tuple
import numpy as np
import pyrealsense2 as rs

class RealSenseStream:
    def __init__(self, color_width: int = 1280, color_height: int = 720,
                 depth_width: int = 1280, depth_height: int = 720,
                 fps: int = 30, warmup_frames: int = 30):
        self._color_w, self._color_h = color_width, color_height
        self._depth_w, self._depth_h = depth_width, depth_height
        self._fps, self._warmup = fps, warmup_frames

        self._pipeline = rs.pipeline()
        self._align    = rs.align(rs.stream.color)
        self._depth_scale: Optional[float] = None
        self._intrinsics: Optional[rs.intrinsics] = None
        self._running  = False

    def start(self) -> None:
        cfg = rs.config()
        cfg.enable_stream(rs.stream.color, self._color_w, self._color_h, rs.format.bgr8, self._fps)
        cfg.enable_stream(rs.stream.depth, self._depth_w, self._depth_h, rs.format.z16, self._fps)

        profile = self._pipeline.start(cfg)
        self._depth_scale = profile.get_device().first_depth_sensor().get_depth_scale()
        self._intrinsics  = profile.get_stream(rs.stream.color).as_video_stream_profile().get_intrinsics()

        for _ in range(self._warmup): self._pipeline.wait_for_frames()
        self._running = True

    def stop(self) -> None:
        if self._running:
            self._pipeline.stop()
            self._running = False

    def get_aligned_frames(self) -> Optional[Tuple[np.ndarray, np.ndarray, object, object, float]]:
        if not self._running: return None
        frames  = self._pipeline.wait_for_frames()
        aligned = self._align.process(frames)
        
        color_frame, depth_frame = aligned.get_color_frame(), aligned.get_depth_frame()
        if not color_frame or not depth_frame: return None

        return (np.asanyarray(color_frame.get_data()), np.asanyarray(depth_frame.get_data()),
                depth_frame, self._intrinsics, self._depth_scale)

    @property
    def intrinsics(self) -> Optional[object]: return self._intrinsics
    @property
    def depth_scale(self) -> Optional[float]: return self._depth_scale
    @property
    def is_running(self) -> bool: return self._running

    def __enter__(self):
        self.start()
        return self
    def __exit__(self, *_): self.stop()