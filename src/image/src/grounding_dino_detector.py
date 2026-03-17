#!/usr/bin/env python3
"""
grounding_dino_detector.py
==========================
GroundingDINO 物體偵測封裝模組。

職責（單一功能）：
    管理 GroundingDINO 模型的載入與推論，
    將推論結果轉換為標準化的 dict 列表回傳。

此模組不依賴 ROS，也不做任何 3D 幾何計算或相機操作。
"""
from typing import List, Dict
import cv2
import numpy as np
import torch
import warnings
from PIL import Image as PILImage

from groundingdino.util.inference import load_model, predict
import groundingdino.datasets.transforms as T


# 影像前處理 transform（GroundingDINO 標準）
_TRANSFORM = T.Compose([
    T.RandomResize([800], max_size=1333),
    T.ToTensor(),
    T.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
])


class GroundingDINODetector:
    """
    GroundingDINO 模型封裝器。

    用法:
        detector = GroundingDINODetector(config_path, weights_path)
        detections = detector.detect(bgr_image, "cup")
        # detections: [{'bbox': (x1,y1,x2,y2), 'confidence': 0.82, 'phrase': 'cup'}, ...]
    """

    def __init__(self,
                 config_path:  str,
                 weights_path: str,
                 device:       str = None):
        """
        參數:
            config_path  : GroundingDINO config .py 路徑
            weights_path : 模型權重 .pth 路徑
            device       : 'cuda' 或 'cpu'，None 則自動選擇
        """
        if device is None:
            device = "cuda" if torch.cuda.is_available() else "cpu"

        if device == "cuda":
            if not torch.cuda.is_available():
                warnings.warn(
                    "要求使用 CUDA，但目前不可用，已自動改用 CPU 推論。"
                )
                device = "cpu"
            else:
                try:
                    import groundingdino
                    has_custom_ops = hasattr(groundingdino, "_C")
                except Exception:
                    has_custom_ops = False

                if not has_custom_ops:
                    warnings.warn(
                        "GroundingDINO custom ops (_C) 不可用，將使用 PyTorch fallback 於 GPU 推論。"
                    )

        self._device = device
        self._model  = load_model(config_path, weights_path, device=device)

    # ── 公開介面 ──────────────────────────────────────────────────────────

    def detect(self,
               bgr_image:   np.ndarray,
               text_prompt: str,
               box_threshold:  float = 0.30,
               text_threshold: float = 0.25) -> List[Dict]:
        """
        對 BGR 影像執行 GroundingDINO 推論，偵測指定文字描述的物體。

        參數:
            bgr_image      : BGR numpy array（HxWx3）
            text_prompt    : 要偵測的物品名稱，例如 "cup"
            box_threshold  : Bounding box 信心度門檻
            text_threshold : 文字對應信心度門檻

        回傳:
            List[Dict]，每個 dict 包含：
                'bbox'      : (x1, y1, x2, y2)  像素座標（int）
                'confidence': float
                'phrase'    : str
        """
        h, w = bgr_image.shape[:2]
        image_tensor = self._preprocess(bgr_image)

        boxes, confidences, phrases = predict(
            model          = self._model,
            image          = image_tensor,
            caption        = text_prompt,
            box_threshold  = box_threshold,
            text_threshold = text_threshold,
            device         = self._device,
        )

        results = []
        if len(boxes) == 0:
            return results

        boxes_np = boxes.cpu().numpy()
        confs_np = confidences.cpu().numpy()

        for box, conf, phrase in zip(boxes_np, confs_np, phrases):
            cx_n, cy_n, bw_n, bh_n = box
            x1 = max(0,     int((cx_n - bw_n / 2) * w))
            y1 = max(0,     int((cy_n - bh_n / 2) * h))
            x2 = min(w - 1, int((cx_n + bw_n / 2) * w))
            y2 = min(h - 1, int((cy_n + bh_n / 2) * h))

            results.append({
                'bbox':       (x1, y1, x2, y2),
                'confidence': float(conf),
                'phrase':     phrase,
            })

        return results

    # ── 私有方法 ──────────────────────────────────────────────────────────

    @staticmethod
    def _preprocess(bgr_image: np.ndarray):
        """BGR numpy array → GroundingDINO 所需 tensor。"""
        rgb     = cv2.cvtColor(bgr_image, cv2.COLOR_BGR2RGB)
        pil_img = PILImage.fromarray(rgb)
        tensor, _ = _TRANSFORM(pil_img, None)
        return tensor

    @property
    def device(self) -> str:
        return self._device
