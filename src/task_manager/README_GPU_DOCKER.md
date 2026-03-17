# GPU Docker 環境建置指南
## RTX 3090 Ti + ROS Noetic + GroundingDINO Swin-B + RealSense D456/D435i

---

## ⚠️ 關於你現有的程式碼

**不會消失，也不會受影響。**

- 你原本的容器 `aiRobots`（現有環境）**繼續存在、繼續可以跑**
- 新容器透過 `-v /root/catkin_ws/src:/root/catkin_ws/src` 掛載同一份程式碼
- 兩個容器**共享同一個 `/root/catkin_ws/src` 目錄**
- 在新容器裡 `git push` 的程式碼，舊容器也看得到（因為是同一個資料夾）

---

## 步驟一：在主機上安裝 nvidia-container-toolkit（只需做一次）

在**主機終端機**（不是容器內）執行：

```bash
# 加入 NVIDIA 容器工具套件 repo
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
  sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
  sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

# 安裝
sudo apt-get update && sudo apt-get install -y nvidia-container-toolkit

# 設定 Docker 使用 nvidia runtime
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker

# 驗證（應該看到 GPU 資訊）
docker run --rm --gpus all nvidia/cuda:12.2.2-base-ubuntu20.04 nvidia-smi
```

---

## 步驟二：設定 RealSense udev rules（讓容器能存取 USB 相機）

在**主機終端機**執行：

```bash
# 下載並安裝 udev rules
sudo apt-get install -y librealsense2-utils

# 或手動設定
wget -O /tmp/99-realsense-libusb.rules \
  https://raw.githubusercontent.com/IntelRealSense/librealsense/master/config/99-realsense-libusb.rules
sudo cp /tmp/99-realsense-libusb.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules && sudo udevadm trigger

# 插上 D456 或 D435i，確認有偵測到
rs-enumerate-devices   # 如果有安裝 librealsense2-utils
```

---

## 步驟三：建置 GPU Docker image

在**主機終端機**，進入放有 Dockerfile.gpu 的目錄：

```bash
cd /root/catkin_ws/src/task_manager

# 建置 image（第一次約需 15-30 分鐘，主要是下載 PyTorch 和 CUDA）
docker compose -f docker-compose.gpu.yml build

# 確認 image 建置成功
docker images | grep ros_noetic_gpu
```

---

## 步驟四：啟動新容器

```bash
# 啟動（背景執行）
docker compose -f docker-compose.gpu.yml up -d

# 進入容器
docker exec -it aiRobots_Dong bash

# ─── 容器內驗證 GPU ───
nvidia-smi                                          # 應看到 RTX 3090 Ti
python3 -c "import torch; print(torch.cuda.get_device_name(0))"  # RTX 3090 Ti
python3 -c "import pyrealsense2 as rs; print(rs.__version__)"    # RealSense 版本
```

---

## 步驟五：在新容器內建置 Catkin workspace

```bash
# 進入容器後
source /opt/ros/noetic/setup.bash
cd /root/catkin_ws

# 如果 src 是空的（第一次）
cd src && git clone https://github.com/CiDongCheng/ros_llm_robot.git .

# 建置
cd /root/catkin_ws && catkin_make

source devel/setup.bash
```

---

## 步驟六：用 VS Code 連線進新容器（Dev Container）

1. 在主機打開 VS Code
2. 安裝擴充套件 **"Dev Containers"**（ms-vscode-remote.remote-containers）
3. 確認新容器已啟動：`docker ps | grep aiRobots_Dong`
4. VS Code 左下角點「><」→ **"Attach to Running Container..."**
5. 選擇 `aiRobots_Dong`
6. 開啟資料夾 `/root/catkin_ws`

---

## 兩個容器並存示意圖

```
主機 (RTX 3090 Ti)
├── /root/catkin_ws/src/          ← 共享目錄（兩個容器都掛這個）
│     ├── task_manager/
│     ├── dabc_optimizer/
│     ├── image/
│     └── GroundingDINO/
│
├── 容器: aiRobots               ← 舊容器（純 CPU ROS）繼續存在可以跑
│     └── 掛載 /root/catkin_ws/src （只讀跑 ROS task manager）
│
└── 容器: aiRobots_Dong           ← 新容器（GPU + GroundingDINO）
      ├── CUDA 12.2 + RTX 3090 Ti
      ├── GroundingDINO Swin-B
      ├── RealSense D456 / D435i
      └── 掛載 /root/catkin_ws/src （共享同一份程式碼）
```

---

## 常用指令速查

```bash
# 啟動 GPU 容器
docker compose -f /root/catkin_ws/src/task_manager/docker-compose.gpu.yml up -d

# 進入 GPU 容器
docker exec -it aiRobots_Dong bash

# 停止 GPU 容器
docker compose -f /root/catkin_ws/src/task_manager/docker-compose.gpu.yml down

# 查看容器狀態
docker ps

# 查看 GPU 容器 log
docker logs aiRobots_Dong
```

---

## 注意事項

| 項目 | 說明 |
|------|------|
| **原有容器** | `aiRobots` 完全不受影響，繼續存在 |
| **程式碼** | 兩個容器共享同一份 `/root/catkin_ws/src`，不會重複 |
| **模型權重** | 存放在 Docker named volume `grounding_dino_weights`，重建容器不會消失 |
| **相機** | D456/D435i 需要插在主機 USB 3.0 孔，且主機要先設好 udev rules |
| **CUDA 版本** | 使用 CUDA 12.2（對應主機驅動 535.183.01 ✅） |
| **git push** | 新容器需要 SSH key，已透過 devcontainer.json 掛載 `~/.ssh` |
