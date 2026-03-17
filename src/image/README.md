# Cup 3D Detector — GroundingDINO-SwinB + RealSense D456

使用 **GroundingDINO-SwinB** 對 Intel RealSense **D456 RGBD 相機**的畫面進行開放詞彙物件偵測，
自動抓取「杯子」並輸出其相機座標系下的三維座標 **(X, Y, Z)**。

---

## 檔案結構

```
image/
├── cup_detector.py   # 主程式
├── config.yaml       # 可調整的設定參數
└── README.md         # 本說明文件
```

---

## 環境需求

| 項目 | 版本 |
|------|------|
| Python | 3.8+ |
| PyTorch | 2.x + CUDA |
| groundingdino | 0.1.0（已安裝於 `/opt/GroundingDINO`）|
| pyrealsense2 | 2.55+ |
| opencv-python | 4.x |

---

## 模型權重位置

```
/opt/GroundingDINO/weights/groundingdino_swinb_cogcoor.pth
```

若需更換，請修改 `cup_detector.py` 頂部的 `GROUNDING_DINO_WEIGHTS` 變數。

---

## 執行方式

```bash
cd /root/catkin_ws/src/image
python3 cup_detector.py
```

---

## 輸出說明

### 終端機輸出

每偵測到杯子時，會印出：

```
[DETECT] cup (conf=0.812) | BBox=(423,210)-(687,520) | 3D: X=0.032m  Y=0.015m  Z=0.845m
```

| 欄位 | 說明 |
|------|------|
| `conf` | bounding box 信心度 |
| `BBox` | 畫面上的像素範圍 |
| `X` | 相機座標系 左(-) / 右(+)，單位公尺 |
| `Y` | 相機座標系 上(-) / 下(+)，單位公尺 |
| `Z` | 與相機的距離（深度），單位公尺 |

### 視窗顯示

- 綠色框：偵測到的杯子
- 框頂標籤：物體名稱、信心度、三維座標
- 左上角：即時 FPS 與偵測目標

按下 **`q`** 退出程式。

---

## 三維座標計算原理

1. GroundingDINO 取得 bounding box（正規化 cx, cy, w, h）
2. 將 bbox 轉回像素座標，對齊深度圖（`rs.align` 對齊至彩色）
3. 在 bbox **中心 50% 區域**取深度值的**中位數**（過濾邊緣雜訊）
4. 利用相機內參反投影：

$$X = \frac{(u - c_x)}{f_x} \cdot Z, \quad Y = \frac{(v - c_y)}{f_y} \cdot Z$$

---

## 調整偵測目標

修改 `cup_detector.py` 中的 `TEXT_PROMPT`，例如：

```python
TEXT_PROMPT = "bottle"          # 單一物體
TEXT_PROMPT = "cup . bottle"    # 多物體（用 . 分隔）
```
