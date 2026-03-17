#!/usr/bin/env python3
"""
depth_geometry.py
=================
3D 幾何計算工具模組。

職責（單一功能）：
    - BBox 中心區域取中位數深度
    - 用中心深度計算圓柱形物體半徑 R
    - BBox 中心像素反投影為表面 XYZ 座標

改動備註：已完全解除對 pyrealsense2 函式庫的依賴，支援跨平台與 ROS 矩陣運算。
"""
from typing import Optional, Tuple, Dict
import numpy as np

DEPTH_MIN_M = 0.1
DEPTH_MAX_M = 5.0

# [已停用] pixel_to_3d 依賴 rs.depth_frame 原生物件，在 ROS 影像流中無法使用，已註解保留供參考。
# def pixel_to_3d(depth_frame, intrinsics, u: float, v: float): ...

def get_median_depth_in_box(depth_image: np.ndarray,
                             x1: int, y1: int, x2: int, y2: int,
                             depth_scale: float) -> Optional[float]:
    """在 BBox 中心 25% 區域取深度中位數，過濾邊緣雜訊。"""
    cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
    half_w = max(1, (x2 - x1) // 4)
    half_h = max(1, (y2 - y1) // 4)

    rx1, rx2 = max(0, cx - half_w), min(depth_image.shape[1] - 1, cx + half_w)
    ry1, ry2 = max(0, cy - half_h), min(depth_image.shape[0] - 1, cy + half_h)

    roi = depth_image[ry1:ry2, rx1:rx2].astype(np.float32) * depth_scale
    valid = roi[(roi > DEPTH_MIN_M) & (roi < DEPTH_MAX_M)]

    return float(np.median(valid)) if valid.size > 0 else None

def compute_object_radius_3d(intrinsics_dict: Dict[str, float],
                              x1: int, y1: int, x2: int, y2: int,
                              depth_z: float) -> float:
    """
    用中心深度值 (depth_z) 將 BBox 左右兩邊像素反投影為 3D 點，計算半徑 R。
    參數 intrinsics_dict 格式: {'fx': float, 'fy': float, 'ppx': float, 'ppy': float}
    """
    fx, fy = intrinsics_dict['fx'], intrinsics_dict['fy']
    ppx, ppy = intrinsics_dict['ppx'], intrinsics_dict['ppy']
    
    v_center = (y1 + y2) / 2.0

    pt_left = np.array([
        (float(x1) - ppx) / fx * depth_z,
        (v_center  - ppy) / fy * depth_z,
        depth_z
    ])
    pt_right = np.array([
        (float(x2) - ppx) / fx * depth_z,
        (v_center  - ppy) / fy * depth_z,
        depth_z
    ])

    diameter = float(np.linalg.norm(pt_right - pt_left))
    return diameter / 2.0

def get_surface_xyz(intrinsics_dict: Dict[str, float],
                    x1: int, y1: int, x2: int, y2: int,
                    depth_median: float) -> Tuple[float, float, float]:
    """將 BBox 中心像素用中位數深度反投影，取得物體表面中心 3D 座標。"""
    fx, fy = intrinsics_dict['fx'], intrinsics_dict['fy']
    ppx, ppy = intrinsics_dict['ppx'], intrinsics_dict['ppy']
    
    u_center = (x1 + x2) / 2.0
    v_center = (y1 + y2) / 2.0

    X = (u_center - ppx) / fx * depth_median
    Y = (v_center - ppy) / fy * depth_median
    Z = depth_median
    return (X, Y, Z)