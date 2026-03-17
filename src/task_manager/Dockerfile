# 使用官方的 ROS Noetic Desktop Full 版本
FROM osrf/ros:noetic-desktop-full

# 設定環境變數
ENV DEBIAN_FRONTEND=noninteractive

# 1. 安裝系統基本工具
RUN apt-get update && apt-get install -y \
    python3-pip \
    python3-dev \
    python3-catkin-tools \
    git \
    nano \
    net-tools \
    wget \
    && rm -rf /var/lib/apt/lists/*

# 2. 升級 pip 並安裝 Python 函式庫
# === 關鍵修改：指定 openai 版本 ===
# 我們將 openai 指定為 1.12.0 (或 1.30.0 以下)，這個版本支援 Python 3.8 且夠新能跑 GPT-4o
RUN pip3 install --upgrade pip && \
    pip3 install --no-cache-dir \
    "openai==1.12.0" \
    "pydantic<2.6.0" \
    python-dotenv \
    colorama \
    rospkg \
    numpy

# 3. 建立 Catkin Workspace
WORKDIR /root/catkin_ws
RUN mkdir -p /root/catkin_ws/src

# 4. 初始化工作空間
RUN /bin/bash -c "source /opt/ros/noetic/setup.bash && catkin_make"

# 5. 設定環境變數
RUN echo "source /opt/ros/noetic/setup.bash" >> /root/.bashrc
RUN echo "source /root/catkin_ws/devel/setup.bash" >> /root/.bashrc

# 6. 設定工作目錄
WORKDIR /root/catkin_ws

CMD ["bash"]
