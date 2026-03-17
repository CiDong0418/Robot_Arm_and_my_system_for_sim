#!/usr/bin/env python3
"""
test_offline.py
===============
離線測試腳本：不需要 D456 相機。
從網路下載或使用本地圖片，測試 GroundingDINO-SwinB 能否正確偵測杯子。

執行：
    python3 test_offline.py                    # 使用預設網路圖片
    python3 test_offline.py --image my.jpg     # 使用本地圖片
"""

import sys
import argparse
import urllib.request
import cv2
import numpy as np
import torch
from PIL import Image as PILImage
from groundingdino.util.inference import load_model, predict
import groundingdino.datasets.transforms as T

# ── 設定 ──
GROUNDING_DINO_CONFIG  = "/opt/GroundingDINO/groundingdino/config/GroundingDINO_SwinB_cfg.py"
GROUNDING_DINO_WEIGHTS = "/opt/GroundingDINO/weights/groundingdino_swinb_cogcoor.pth"
DEVICE         = "cuda" if torch.cuda.is_available() else "cpu"
BOX_THRESHOLD  = 0.30
TEXT_THRESHOLD = 0.25
TEXT_PROMPT    = "cup"

# 測試用的圖片網址（COCO 資料集範例，有杯子）
TEST_IMAGE_URL = (
    "https://upload.wikimedia.org/wikipedia/commons/thumb/4/45/"
    "A_small_cup_of_coffee.JPG/640px-A_small_cup_of_coffee.JPG"
)
TEST_IMAGE_PATH = "/tmp/test_cup.jpg"

_TRANSFORM = T.Compose([
    T.RandomResize([800], max_size=1333),
    T.ToTensor(),
    T.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
])


def download_test_image():
    print(f"[INFO] 下載測試圖片: {TEST_IMAGE_URL}")
    try:
        urllib.request.urlretrieve(TEST_IMAGE_URL, TEST_IMAGE_PATH)
        print(f"[INFO] 已儲存至 {TEST_IMAGE_PATH}")
        return TEST_IMAGE_PATH
    except Exception as e:
        print(f"[ERROR] 下載失敗: {e}")
        print("[INFO] 請手動提供圖片，使用 --image 參數。")
        sys.exit(1)


def preprocess(bgr_image: np.ndarray):
    rgb = cv2.cvtColor(bgr_image, cv2.COLOR_BGR2RGB)
    pil_img = PILImage.fromarray(rgb)
    transformed, _ = _TRANSFORM(pil_img, None)
    return transformed


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", type=str, default=None,
                        help="本地圖片路徑（不指定則自動下載測試圖）")
    parser.add_argument("--prompt", type=str, default=TEXT_PROMPT,
                        help=f"偵測目標文字（預設: '{TEXT_PROMPT}'）")
    parser.add_argument("--box-thresh", type=float, default=BOX_THRESHOLD)
    parser.add_argument("--text-thresh", type=float, default=TEXT_THRESHOLD)
    args = parser.parse_args()

    # ── 準備圖片 ──
    image_path = args.image if args.image else download_test_image()
    bgr = cv2.imread(image_path)
    if bgr is None:
        print(f"[ERROR] 無法讀取圖片: {image_path}")
        sys.exit(1)
    h, w = bgr.shape[:2]
    print(f"[INFO] 圖片大小: {w}x{h}")

    # ── 載入模型 ──
    print(f"[INFO] 裝置: {DEVICE}")
    print("[INFO] 載入 GroundingDINO-SwinB 模型...")
    model = load_model(GROUNDING_DINO_CONFIG, GROUNDING_DINO_WEIGHTS, device=DEVICE)
    print("[INFO] 模型載入完成。")

    # ── 推論 ──
    print(f"[INFO] 偵測目標: '{args.prompt}'")
    image_tensor = preprocess(bgr)
    boxes, confidences, phrases = predict(
        model          = model,
        image          = image_tensor,
        caption        = args.prompt,
        box_threshold  = args.box_thresh,
        text_threshold = args.text_thresh,
        device         = DEVICE,
    )

    print(f"\n[結果] 共偵測到 {len(boxes)} 個目標")

    # ── 繪製結果 ──
    result = bgr.copy()
    if len(boxes) > 0:
        boxes_np = boxes.cpu().numpy()
        confs_np = confidences.cpu().numpy()

        for i, (box, conf, phrase) in enumerate(zip(boxes_np, confs_np, phrases)):
            cx_n, cy_n, bw_n, bh_n = box
            x1 = int((cx_n - bw_n / 2) * w)
            y1 = int((cy_n - bh_n / 2) * h)
            x2 = int((cx_n + bw_n / 2) * w)
            y2 = int((cy_n + bh_n / 2) * h)
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(w-1, x2), min(h-1, y2)

            print(f"  [{i+1}] {phrase}  conf={conf:.4f}  BBox=({x1},{y1})-({x2},{y2})")

            # 畫框
            cv2.rectangle(result, (x1, y1), (x2, y2), (0, 255, 0), 2)
            label = f"{phrase} {conf:.2f}"
            (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 1)
            cv2.rectangle(result, (x1, y1 - th - 8), (x1 + tw + 4, y1), (0, 255, 0), -1)
            cv2.putText(result, label, (x1+2, y1-4),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 1, cv2.LINE_AA)
    else:
        print("  (沒有偵測到目標，可嘗試降低 --box-thresh)")

    # ── 儲存結果 ──
    out_path = "/tmp/test_result.jpg"
    cv2.imwrite(out_path, result)
    print(f"\n[INFO] 結果已儲存至: {out_path}")

    # ── 嘗試顯示視窗 ──
    import os
    if os.environ.get("DISPLAY"):
        try:
            cv2.imshow("GroundingDINO Test Result", result)
            print("[INFO] 按任意鍵關閉視窗...")
            cv2.waitKey(0)
            cv2.destroyAllWindows()
        except Exception:
            pass
    else:
        print(f"[INFO] 無顯示器（headless），結果圖片已儲存至: {out_path}")


if __name__ == "__main__":
    main()
