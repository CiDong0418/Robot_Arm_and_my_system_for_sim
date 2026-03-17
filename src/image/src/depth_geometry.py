#!/usr/bin/env python3
"""
depth_geometry.py
=================
3D 幾何計算工具模組。

職責（單一功能）：
    - 像素座標 + 深度 → 相機座標系 3D 點
    - BBox 中心區域取中位數深度
    - 用中心深度計算圓柱形物體半徑 R
    - BBox 中心像素反投影為表面 XYZ 座標

此模組不依賴 ROS，也不依賴相機硬體，只做純數學運算。
"""
from typing import Optional, Tuple
import numpy as np

# 深度有效範圍 (公尺)
DEPTH_MIN_M = 0.1
DEPTH_MAX_M = 5.0


def pixel_to_3d(depth_frame, intrinsics,
                u: float, v: float) -> Optional[Tuple[float, float, float]]:
    """
    利用 RealSense 內參，將像素座標 (u, v) 反投影為相機座標系 (X, Y, Z)。

    參數:
        depth_frame : rs.depth_frame
        intrinsics  : rs.intrinsics（彩色相機）
        u, v        : 像素座標（float）

    回傳:
        (X, Y, Z) 單位公尺；若深度無效則回傳 None。
    """
    import pyrealsense2 as rs
    depth_m = depth_frame.get_distance(int(u), int(v))
    if depth_m <= DEPTH_MIN_M or depth_m >= DEPTH_MAX_M:
        return None
    point = rs.rs2_deproject_pixel_to_point(intrinsics, [u, v], depth_m)
    return tuple(point)


def get_median_depth_in_box(depth_image: np.ndarray,
                             x1: int, y1: int, x2: int, y2: int,
                             depth_scale: float) -> Optional[float]:
    """
    在 BBox 中心 25% 區域取深度中位數，過濾邊緣雜訊。

    參數:
        depth_image : uint16 深度影像
        x1,y1,x2,y2: BBox 像素座標
        depth_scale : RealSense 深度比例（raw unit → 公尺）

    回傳:
        中位數深度（公尺）；若無有效深度回傳 None。
    """
    cx = (x1 + x2) // 2
    cy = (y1 + y2) // 2
    half_w = max(1, (x2 - x1) // 4)
    half_h = max(1, (y2 - y1) // 4)

    rx1 = max(0, cx - half_w)
    rx2 = min(depth_image.shape[1] - 1, cx + half_w)
    ry1 = max(0, cy - half_h)
    ry2 = min(depth_image.shape[0] - 1, cy + half_h)

    roi = depth_image[ry1:ry2, rx1:rx2].astype(np.float32) * depth_scale
    valid = roi[(roi > DEPTH_MIN_M) & (roi < DEPTH_MAX_M)]

    if valid.size == 0:
        return None
    return float(np.median(valid))


def compute_object_radius_3d(intrinsics,
                              x1: int, y1: int, x2: int, y2: int,
                              depth_z: float) -> float:
    """
    用中心深度值 (depth_z) 將 BBox 左右兩邊像素反投影為 3D 點，計算半徑 R。

    說明：
        BBox 邊緣像素常落在物體輪廓與背景交界，邊緣深度容易取到背景值
        導致 R 暴增。改用穩定的中心深度值對兩邊像素做反投影：
            X_left  = (x1 - ppx) / fx * depth_z
            X_right = (x2 - ppx) / fx * depth_z
        兩點 Z 相同，距離純粹為橫向寬度，不受邊緣雜訊影響。

    參數:
        intrinsics  : rs.intrinsics（彩色相機）
        x1,y1,x2,y2: BBox 像素座標
        depth_z     : 表面中心深度（公尺），通常使用 depth_median

    回傳:
        R（float，公尺），永遠有效。
    """
    v_center = (y1 + y2) / 2.0

    pt_left = np.array([
        (float(x1) - intrinsics.ppx) / intrinsics.fx * depth_z,
        (v_center  - intrinsics.ppy) / intrinsics.fy * depth_z,
        depth_z
    ])
    pt_right = np.array([
        (float(x2) - intrinsics.ppx) / intrinsics.fx * depth_z,
        (v_center  - intrinsics.ppy) / intrinsics.fy * depth_z,
        depth_z
    ])

    diameter = float(np.linalg.norm(pt_right - pt_left))
    return diameter / 2.0


def get_surface_xyz(intrinsics,
                    x1: int, y1: int, x2: int, y2: int,
                    depth_median: float) -> Tuple[float, float, float]:
    """
    將 BBox 中心像素用中位數深度反投影，取得物體表面中心 3D 座標。

    參數:
        intrinsics  : rs.intrinsics（彩色相機）
        x1,y1,x2,y2: BBox 像素座標
        depth_median: 表面中心深度（公尺）

    回傳:
        (X, Y, Z) 相機座標系（公尺）
    """
    u_center = (x1 + x2) / 2.0
    v_center = (y1 + y2) / 2.0

    X = (u_center - intrinsics.ppx) / intrinsics.fx * depth_median
    Y = (v_center - intrinsics.ppy) / intrinsics.fy * depth_median
    Z = depth_median
    return (X, Y, Z)
