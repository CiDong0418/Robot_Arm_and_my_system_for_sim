# ROS 語音節點：全新環境重建指南

這份指南記錄了如何從零開始（在一台全新的 Linux 或 Docker 容器中）重建 `voice_node.py` 的運行環境，包含我們為了解決「麥克風硬體佔用」與「找不到模型」所做的所有關鍵設定。

---

## 步驟一：安裝系統級別的音效依賴庫 (apt)

在安裝 PyAudio 之前，你的 Linux 系統必須要有 ALSA 音效伺服器的底層標頭檔。
請先在終端機執行：

```bash
sudo apt-get update
sudo apt-get install -y portaudio19-dev python3-pyaudio alsa-utils
```
> [!NOTE] 
> - `portaudio19-dev`: 這是 `pyaudio` 可以順利安裝的關鍵底層。
> - `alsa-utils`: 我們用來測試麥克風硬體如 `arecord -l` 和 `aplay` 的工具包。

---

## 步驟二：安裝 Python 核心套件 (pip)

你的 ROS 節點 (`voice_node.py` 等) 主要依賴以下幾個關鍵套件：

```bash
pip install pyaudio numpy openwakeword webrtcvad openai
```
> [!NOTE] 
> - `pyaudio` 與 `numpy`: 負責從麥克風撈出數據與轉換。
> - `openwakeword`: 我們用來聽「阿布」的離線喚醒詞引擎。
> - `webrtcvad`: 我們用來判斷什麼時候「講完話」的靜音偵測庫。
> - `openai`: 負責將錄音送上雲端轉譯成文字。

---

## 步驟三：🌟 關鍵防雷指令（下載基底模型）

這是你今天稍早提到的重要步驟！
`openwakeword` 在第一次執行時，會偷偷嘗試去網路上下載它分析聲音所需的「特徵萃取基底模型」（例如 `melspectrogram.onnx`）。但如果在 Docker 內或是網路不穩的情況下，很容易卡住或崩潰。

為了確保環境一建好就能馬上用，請務必在**安裝套件後，直接手動觸發下載**：

```bash
python3 -c "from openwakeword.utils import download_models; download_models()"
```
> [!TIP]
> 如果你是寫 `Dockerfile`，強烈建議把上面這兩行（pip install 和 python3 -c）寫進去，這樣打出來的 Docker Image 裡面就會自帶那些模型檔案，節點一開就能無腦跑！

---

## 步驟四：修正 ALSA 系統預設硬體佔用問題 (選項)

雖然我們已經在 Python 寫了超級強大的自動重連避障機制，但如果你的系統預設音效卡一直抓不到 USB，最穩的做法就是告訴 Linux：**請強制作為第一順位的預設錄音設備是卡號 2（你的 USB 麥克風）**。

在你的家目錄 (`~`) 底下建立一個 `~/.asoundrc` 設定檔，內容永遠只要最簡單的兩行：

```bash
cat << 'EOF' > ~/.asoundrc
defaults.pcm.card 2
defaults.ctl.card 2
EOF
```
*(注意：這裡的 `2` 是基於你在 `arecord -l` 看到的 `card 2: Sum13 [Sum-13], device 0: USB Audio`。如果你換了電腦，卡號可能會變成 `1` 或 `0`，請用 `arecord -l` 確認後修改。)*

---

## 步驟五：設定環境變數 (.env) 

你的程式碼 (`whisper_transcriber.py`) 會自動去同一個資料夾找 OpenAI 的金鑰。
確保你在這兩個檔案的同一層，有一個不可被推上 Git 的 `.env` 檔：

```bash
nano /root/catkin_ws/src/voice/src/.env
```
內容填入：
```
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxx...
```

---

## ✅ 完成！測試執行

當你到達新電腦後，走完上述的五個步驟，就能完美還原今天的狀態，直接下達終極指令：
```bash
rosrun voice voice_node.py
```
它就會直接抓取你的 `abu.onnx` 模型，並開始監聽「阿布」以及對接大腦了！
