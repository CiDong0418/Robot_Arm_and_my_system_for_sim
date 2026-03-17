#!/usr/bin/env python3
"""
cup_detector.py 1223
===============
使用 GroundingDINO-SwinB 搭配 Intel RealSense D456 RGBD 相機，
偵測畫面中的「杯子」並輸出其三維座標 (X, Y, Z)。

流程：
  1. 從 D456 取得彩色影像與深度影像
  2. 對彩色影像執行 GroundingDINO 推論，取得 bounding box
  3. 在深度影像中對 bounding box 中心區域取中位數深度
  4. 利用相機內參將像素座標反投影為 3D 座標
  5. 計算圓柱形物體半徑 R，並補償深度取得物體真實體積中心
  6. 在視窗中即時顯示標注結果與座標資訊

按下 'q' 鍵退出程式。
"""
from typing import Optional
import sys
import os
import time

import cv2
import numpy as np
import torch
import pyrealsense2 as rs
from groundingdino.util.inference import load_model, predict
import groundingdino.datasets.transforms as T
from PIL import Image as PILImage

# 是否有可用的顯示器
_has_display = bool(os.environ.get("DISPLAY", ""))
# ─────────────────────── 設定區 ───────────────────────
# GroundingDINO 模型相關路徑
GROUNDING_DINO_CONFIG = "/opt/GroundingDINO/groundingdino/config/GroundingDINO_SwinB_cfg.py"
GROUNDING_DINO_WEIGHTS = "/opt/GroundingDINO/weights/groundingdino_swinb_cogcoor.pth"

# 推論參數
TEXT_PROMPT    = "cup"   # 要偵測的物體
BOX_THRESHOLD  = 0.30    # bounding box 信心度門檻
TEXT_THRESHOLD = 0.25    # 文字對應信心度門檻
DEVICE         = "cuda" if torch.cuda.is_available() else "cpu"

# D456 串流解析度 / 幀率
COLOR_WIDTH  = 1280
COLOR_HEIGHT = 720
DEPTH_WIDTH  = 1280
DEPTH_HEIGHT = 720
FPS          = 30

# 深度有效範圍 (公尺)
DEPTH_MIN_M = 0.1
DEPTH_MAX_M = 5.0

# ─────────────────────── 影像前處理 ───────────────────────
_TRANSFORM = T.Compose([
    T.RandomResize([800], max_size=1333),
    T.ToTensor(),
    T.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
])

def preprocess_image(bgr_image: np.ndarray):
    """將 BGR numpy array 轉換為 GroundingDINO 所需的 tensor。"""
    rgb = cv2.cvtColor(bgr_image, cv2.COLOR_BGR2RGB)
    pil_img = PILImage.fromarray(rgb)
    transformed, _ = _TRANSFORM(pil_img, None)
    return transformed


# ─────────────────────── 3D 反投影 ───────────────────────
def pixel_to_3d(depth_frame, intrinsics, u: float, v: float) -> tuple:
    """
    利用 RealSense 內參，將像素座標 (u, v) 反投影為相機座標系 (X, Y, Z)。

    參數:
        depth_frame : rs.depth_frame
        intrinsics  : rs.intrinsics (彩色相機)
        u, v        : 像素座標 (float)

    回傳:
        (X, Y, Z) 單位公尺；若深度無效則回傳 None。
    """
    depth_m = depth_frame.get_distance(int(u), int(v))
    if depth_m <= DEPTH_MIN_M or depth_m >= DEPTH_MAX_M:
        return None

    point = rs.rs2_deproject_pixel_to_point(intrinsics, [u, v], depth_m)
    return tuple(point)  # (X, Y, Z) in metres


def get_median_depth_in_box(depth_image: np.ndarray,
                             x1: int, y1: int, x2: int, y2: int,
                             depth_scale: float) -> Optional[float]:
    """
    在 bounding box 中心 25% 區域取深度中位數，過濾邊緣雜訊。

    回傳公尺，若無有效深度回傳 None。
    """
    # 取中心 50% 寬高區域
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


# ─────────────────────── 圓柱形物體真實中心計算 ───────────────────────
def compute_object_radius_3d(
        intrinsics,
        x1: int, y1: int, x2: int, y2: int,
        depth_z: float) -> float:
    """
    用中心深度値 (depth_z) 將 BBox 左右兩像素反投影為 3D 點，
    計算物體真實半徑 R。

    為何不用邊緣深度：
        BBox 邊緣像素常落在物體輪廓與背景交界處，
        深度感測在此容易回傳背景深度，導致 R 暴增。

    做法：
        左右邊緣像素的 X 終端機座標：
            X_left  = (x1 - ppx) / fx * depth_z
            X_right = (x2 - ppx) / fx * depth_z
        均使用同一個 depth_z，因此 Z 差為 0，欲式距離純簹為水平廣度：
            diameter = |X_right - X_left| = (x2 - x1) / fx * depth_z
            R = diameter / 2

        這樣 R 只依賴像素寬度與穩定的中心深度，完全不受邊緣深度熾擾影響。

    參數:
        intrinsics  : rs.intrinsics (彩色相機)
        x1, y1, x2, y2 : Bounding Box 像素座標
        depth_z     : 表面中心深度 (公尺)，通常使用 depth_median

    回傳:
        R (float, 公尺)，永遠有效。
    """
    v_center = (y1 + y2) / 2.0

    # 將左右邊緣像素用中心深度反投影為 3D 點
    pt_left  = np.array([
        (float(x1) - intrinsics.ppx) / intrinsics.fx * depth_z,
        (v_center  - intrinsics.ppy) / intrinsics.fy * depth_z,
        depth_z
    ])
    pt_right = np.array([
        (float(x2) - intrinsics.ppx) / intrinsics.fx * depth_z,
        (v_center  - intrinsics.ppy) / intrinsics.fy * depth_z,
        depth_z
    ])

    # Z 相同、Y 相同 → 距離 = |X_right - X_left|
    diameter = float(np.linalg.norm(pt_right - pt_left))
    return diameter / 2.0


def get_object_true_center(
        depth_frame,
        intrinsics,
        x1: int, y1: int, x2: int, y2: int,
        depth_median: float) -> tuple:
    """
    計算圓柱形物體（杯子、水瓶等）的真實體積中心座標。

    問題背景：
        相機量測到的深度是物體「前表面」到相機的距離 Z_surface。
        機械手若要抓取物體正中心，需要夾在距相機更遠的位置：
            Z_true = Z_surface + R
        其中 R 是物體圓形截面的半徑（沿相機 Z 軸方向補償）。

    計算步驟：
        1. 由 BBox 左右邊緣 3D 點算出真實半徑 R
        2. 補償後的真實深度 Z_true = Z_surface + R
        3. 用 Z_true 重新反投影 BBox 中心像素，得到真實體積中心

    參數:
        depth_frame   : rs.depth_frame
        intrinsics    : rs.intrinsics (彩色相機)
        x1,y1,x2,y2  : Bounding Box 像素座標
        depth_median  : 已計算好的表面中位數深度 (公尺)

    回傳:
        dict 包含:
            'xyz_surface' : (X, Y, Z) 表面中心座標 (公尺)
            'xyz_center'  : (X, Y, Z) 物體真實體積中心座標 (公尺)
            'radius_m'    : 半徑 R (公尺)；若計算失敗則為 None
    """
    u_center = (x1 + x2) / 2.0
    v_center = (y1 + y2) / 2.0

    # ── 表面中心（原本的計算方式）──
    X_surf = (u_center - intrinsics.ppx) / intrinsics.fx * depth_median
    Y_surf = (v_center - intrinsics.ppy) / intrinsics.fy * depth_median
    Z_surf = depth_median
    xyz_surface = (X_surf, Y_surf, Z_surf)

    # ── 計算半徑 R（用中心深度反投影邊緣像素，永遠有效）──
    R = compute_object_radius_3d(intrinsics, x1, y1, x2, y2, depth_median)

    if R <= 0.001:          # 極端情況保護（幾乎不會發生）
        return {
            'xyz_surface': xyz_surface,
            'xyz_center' : xyz_surface,
            'radius_m'   : R,
        }

    # ── 真實體積中心：Z 方向加上半徑補償 ──
    #
    #   相機座標系：Z 為光軸（朝物體方向）
    #   物體前緣深度 = Z_surf
    #   物體中心深度 = Z_surf + R
    #
    Z_true = Z_surf + R
    X_true = (u_center - intrinsics.ppx) / intrinsics.fx * Z_true
    Y_true = (v_center - intrinsics.ppy) / intrinsics.fy * Z_true
    xyz_center = (X_true, Y_true, Z_true)

    return {
        'xyz_surface': xyz_surface,
        'xyz_center' : xyz_center,
        'radius_m'   : R,
    }


# ─────────────────────── 視覺化輔助 ───────────────────────
def draw_detection(frame: np.ndarray,
                   x1: int, y1: int, x2: int, y2: int,
                   phrase: str, confidence: float,
                   xyz: Optional[tuple],
                   radius_m: Optional[float] = None) -> None:
    """
    在影像上繪製 bounding box 與座標標注。

    - BBox 上方：物體名稱 + 信心度 + 表面中心 3D 座標 (X, Y, Z)
    - BBox 下方：半徑 R（獨立一行，不與 XYZ 混在一起）
    """
    color = (0, 255, 0)
    thickness = 2

    cv2.rectangle(frame, (x1, y1), (x2, y2), color, thickness)

    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 0.55

    # ── 上方：表面中心座標（純 XYZ，不含 R）──
    if xyz is not None:
        label = (f"{phrase} {confidence:.2f} | "
                 f"X:{xyz[0]:.3f}m Y:{xyz[1]:.3f}m Z:{xyz[2]:.3f}m")
    else:
        label = f"{phrase} {confidence:.2f} | depth N/A"

    (tw, th), _ = cv2.getTextSize(label, font, font_scale, 1)
    cv2.rectangle(frame, (x1, y1 - th - 8), (x1 + tw + 4, y1), color, -1)
    cv2.putText(frame, label, (x1 + 2, y1 - 4),
                font, font_scale, (0, 0, 0), 1, cv2.LINE_AA)

    # ── 下方：半徑 R（獨立另一行）──
    if radius_m is not None:
        r_label = f"R = {radius_m*100:.1f} cm"
        r_color = (0, 200, 255)   # 橘黃色，與上方 XYZ 標注區分
        (rw, rh), _ = cv2.getTextSize(r_label, font, font_scale, 1)
        cv2.rectangle(frame, (x1, y2), (x1 + rw + 4, y2 + rh + 8), r_color, -1)
        cv2.putText(frame, r_label, (x1 + 2, y2 + rh + 2),
                    font, font_scale, (0, 0, 0), 1, cv2.LINE_AA)


# ─────────────────────── 主程式 ───────────────────────
def main():
    # ── 載入模型 ──
    print(f"[INFO] 使用裝置: {DEVICE}")
    print("[INFO] 載入 GroundingDINO-SwinB 模型中...")
    model = load_model(GROUNDING_DINO_CONFIG, GROUNDING_DINO_WEIGHTS, device=DEVICE)
    print("[INFO] 模型載入完成。")

    # ── 初始化 RealSense D456 ──
    pipeline = rs.pipeline()
    config   = rs.config()
    config.enable_stream(rs.stream.color, COLOR_WIDTH, COLOR_HEIGHT,
                         rs.format.bgr8, FPS)
    config.enable_stream(rs.stream.depth, DEPTH_WIDTH, DEPTH_HEIGHT,
                         rs.format.z16, FPS)

    print("[INFO] 啟動 RealSense D456 相機...")
    profile = pipeline.start(config)

    # 取得深度比例 (raw unit → 公尺)
    depth_sensor = profile.get_device().first_depth_sensor()
    depth_scale  = depth_sensor.get_depth_scale()
    print(f"[INFO] 深度比例: {depth_scale:.6f} m/unit")

    # 取得彩色相機內參（對齊後用於反投影）
    align_to     = rs.align(rs.stream.color)

    # 對齊物件：將深度對齊至彩色影像
    color_profile  = profile.get_stream(rs.stream.color)
    color_intrinsics = color_profile.as_video_stream_profile().get_intrinsics()
    print(f"[INFO] 彩色相機解析度: {color_intrinsics.width}x{color_intrinsics.height}")
    print(f"[INFO] 焦距 fx={color_intrinsics.fx:.2f}, fy={color_intrinsics.fy:.2f}")
    print(f"[INFO] 主點 cx={color_intrinsics.ppx:.2f}, cy={color_intrinsics.ppy:.2f}")

    # 穩定暖機：丟棄前幾幀
    for _ in range(30):
        pipeline.wait_for_frames()
    print("[INFO] 相機暖機完成，開始偵測。按 'q' 退出。")

    prev_time = time.time()

    # ── 跨幀 R 緩存：key=(phrase, 量化cx, 量化cy) → 最後一次有效的 R (公尺)
    last_known_R: dict = {}

    try:
        while True:
            # ── 取得影像 ──
            frames        = pipeline.wait_for_frames()
            aligned       = align_to.process(frames)
            color_frame   = aligned.get_color_frame()
            depth_frame   = aligned.get_depth_frame()

            if not color_frame or not depth_frame:
                continue

            color_image = np.asanyarray(color_frame.get_data())   # BGR, HxWx3
            depth_image = np.asanyarray(depth_frame.get_data())   # uint16, HxW

            h, w = color_image.shape[:2]

            # ── GroundingDINO 推論 ──
            image_tensor = preprocess_image(color_image)
            boxes, confidences, phrases = predict(
                model        = model,
                image        = image_tensor,
                caption      = TEXT_PROMPT,
                box_threshold  = BOX_THRESHOLD,
                text_threshold = TEXT_THRESHOLD,
                device       = DEVICE,
            )

            # ── 處理每個偵測結果 ──
            display = color_image.copy()

            if len(boxes) > 0:
                # boxes 為正規化 cx,cy,w,h 格式
                boxes_np = boxes.cpu().numpy()
                confs_np = confidences.cpu().numpy()

                for box, conf, phrase in zip(boxes_np, confs_np, phrases):
                    cx_n, cy_n, bw_n, bh_n = box
                    x1 = int((cx_n - bw_n / 2) * w)
                    y1 = int((cy_n - bh_n / 2) * h)
                    x2 = int((cx_n + bw_n / 2) * w)
                    y2 = int((cy_n + bh_n / 2) * h)

                    # 夾到影像範圍
                    x1, y1 = max(0, x1), max(0, y1)
                    x2, y2 = min(w - 1, x2), min(h - 1, y2)

                    # 計算 BBox 中心
                    u_center = (x1 + x2) / 2.0
                    v_center = (y1 + y2) / 2.0

                    # 先用中位數深度取得較穩定的 Z
                    depth_median = get_median_depth_in_box(
                        depth_image, x1, y1, x2, y2, depth_scale)

                    if depth_median is not None:
                        # ── 計算表面中心 & 半徑 R ──
                        result = get_object_true_center(
                            depth_frame, color_intrinsics,
                            x1, y1, x2, y2, depth_median)

                        xyz_surf = result['xyz_surface']   # 表面中心（輸出主體）
                        R_new    = result['radius_m']       # 本幀計算的 R

                        # ── 跨幀 R 緩存：量化 BBox 中心到 20px 格子當 key ──
                        obj_key = (phrase,
                                   round(u_center / 20) * 20,
                                   round(v_center / 20) * 20)

                        if R_new is not None:              # 有新的有效 R → 更新
                            last_known_R[obj_key] = R_new

                        R = last_known_R.get(obj_key)      # 取緩存（可能仍是 None）

                        # ── 終端機輸出：XYZ 固定印；R 有值才印，N/A 完全靜默 ──
                        print(f"[DETECT] {phrase} (conf={conf:.3f}) | "
                              f"BBox=({x1},{y1})-({x2},{y2}) | "
                              f"表面中心 X={xyz_surf[0]:.3f}m "
                              f"Y={xyz_surf[1]:.3f}m "
                              f"Z={xyz_surf[2]:.3f}m")
                        if R is not None:
                            src = "新測" if R_new is not None else "緩存"
                            print(f"         半徑 R = {R*100:.1f} cm  [{src}]")

                        # 畫面標注：XYZ 用表面中心，R 獨立在 BBox 下方
                        xyz = xyz_surf
                    else:
                        xyz = None
                        R   = last_known_R.get(
                            (phrase,
                             round(u_center / 20) * 20,
                             round(v_center / 20) * 20))
                        # 深度完全無效才印一次警告
                        print(f"[DETECT] {phrase} (conf={conf:.3f}) | "
                              f"BBox=({x1},{y1})-({x2},{y2}) | 深度無效")

                    draw_detection(display, x1, y1, x2, y2, phrase, conf,
                                   xyz, radius_m=R)

            # ── FPS 計算 ──
            curr_time = time.time()
            fps_val   = 1.0 / max(curr_time - prev_time, 1e-6)
            prev_time = curr_time
            cv2.putText(display, f"FPS: {fps_val:.1f}", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 200, 255), 2)
            cv2.putText(display, f"Target: '{TEXT_PROMPT}'", (10, 60),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 200, 255), 2)

            # ── 顯示視窗 ──
            if _has_display:
                try:
                    cv2.imshow("GroundingDINO + D456 | Cup 3D Detection", display)
                    key = cv2.waitKey(1) & 0xFF
                    if key == ord('q'):
                        print("[INFO] 使用者按下 'q'，退出程式。")
                        break
                except cv2.error:
                    pass

    finally:
        pipeline.stop()
        cv2.destroyAllWindows()
        print("[INFO] 程式結束。")


if __name__ == "__main__":
    main()
