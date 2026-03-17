#!/usr/bin/env python3
"""
open_wake_word_detector.py
=====================
openwakeword 喚醒詞偵測模組。

職責（單一功能）：
    持續從麥克風讀取音訊，偵測到指定喚醒詞（如「阿布」）時呼叫回呼函數。
    取代原本的 Porcupine wake_word_detector.py。
"""
import struct
import threading
from typing import Callable, Optional

class OpenWakeWordDetector:
    @staticmethod
    def _find_usb_mic():
        """搜尋名稱含 'USB' 的輸入設備，找到回傳 index，否則回傳 None（使用系統預設）。"""
        import pyaudio
        pa = pyaudio.PyAudio()
        found = None
        for i in range(pa.get_device_count()):
            info = pa.get_device_info_by_index(i)
            if info["maxInputChannels"] > 0 and "usb" in info["name"].lower():
                found = i
                break
        pa.terminate()
        if found is not None:
            print(f"[OpenWakeWord] 偵測到 USB 麥克風，使用設備 ID [{found}]")
        else:
            print("[OpenWakeWord] 未偵測到 USB 麥克風，使用系統預設輸入設備")
        return found

    def __init__(self,
                 keyword_path: str,
                 on_wake:      Callable[[], None],
                 threshold:    float = 0.5,
                 sample_rate:  int = 16000,
                 chunk_size:   int = 1280):
        """
        參數:
            keyword_path : .onnx 自定義關鍵詞檔案路徑
            on_wake      : 偵測到喚醒詞時呼叫的 callback（無參數）
            threshold    : 觸發門檻值 (0.0 ~ 1.0)
            sample_rate  : 麥克風取樣率（openwakeword 預設 16000）
            chunk_size   : 音訊區塊大小（openwakeword 適配 1280）
        """
        import pyaudio
        from openwakeword.model import Model

        # 這裡會自動載入我們訓練好的 ONNX 檔案
        self._model = Model(wakeword_models=[keyword_path], inference_framework="onnx")
        # 取得載入關鍵字模型的內部名稱 (openwakeword 以檔名為 key)
        self._keyword = list(self._model.models.keys())[0]

        self._on_wake     = on_wake
        self._threshold   = threshold
        self._sample_rate = sample_rate
        self._chunk_size  = chunk_size

        self._input_device_index = self._find_usb_mic()

        import os
        # 強制 PyAudio 的 ALSA 介面允許 plug (自動重採樣) 轉換
        
        self._pa = pyaudio.PyAudio()
        
        # 尋找支援重採樣的 ALSA plughw 裝置 (若無則維持預設)
        plug_device_idx = self._input_device_index
        if self._input_device_index is not None:
            # 在 Linux ALSA 中，有時候直接開 input_device_index 會以 hw (硬體原始格式) 開啟
            # 但我們可以透過尋找名稱含有 "USB Audio" 的 default / sysdefault 或是我們手動建立的 plughw 來重採樣
            pass

        try:
            # 我們不再在這裡預先打開 stream，改到背景執行緒自己控制
            pass
        except Exception as e:
            pass

        self._running  = False
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        """啟動背景監聽執行緒。"""
        self._running = True
        self._thread  = threading.Thread(
            target=self._listen_loop, daemon=True, name="OpenWakeWordDetector")
        self._thread.start()

    def stop(self) -> None:
        """停止監聽並釋放資源。"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
        if self._pa is not None:
            self._pa.terminate()

    def _listen_loop(self) -> None:
        """持續讀取麥克風並交給 openwakeword 判斷。即使設備中途被佔用也能重啟。"""
        import numpy as np
        import pyaudio
        import time
        import rospy
        
        cooldown_seconds = 2.0
        last_trigger_time = 0.0

        rospy.loginfo(f"[OpenWakeWord] 🎤 開始監聽麥克風 (Target={self._keyword}, Threshold={self._threshold})")
        
        frame_count = 0
        while self._running:
            stream = None
            try:
                # 確保 self._pa 存在
                if self._pa is None:
                    self._pa = pyaudio.PyAudio()
                    
                stream = self._pa.open(
                    rate             = self._sample_rate,
                    channels         = 1,
                    format           = self._pa.get_format_from_width(2),
                    input            = True,
                    frames_per_buffer = self._chunk_size,
                )
                
                while self._running:
                    # 讀取音訊資料 (16-bit PCM)，如果 overflow 發生我們直接忽略並繼續
                    raw = stream.read(self._chunk_size, exception_on_overflow=False)
                    pcm = np.frombuffer(raw, dtype=np.int16)
                    
                    # 偵測靜音/過低的音量 (表示 dmix 取不到音訊)
                    if np.abs(pcm).mean() < 10:
                        # 假如有別人(VADRecorder)正在搶 Mic，音量可能變成接近 0
                        # 我們就當成沒收到聲音處理，不預測，降低 CPU 使用率
                        time.sleep(0.01)
                        continue
                        
                    # 進行預測
                    prediction = self._model.predict(pcm)
                    
                    # 取得該關鍵字的最新信心分數
                    score = prediction.get(self._keyword, 0.0)
                    current_time = time.time()
                    
                    frame_count += 1
                    if frame_count % 30 == 0: # 大約每秒印一次 (16000/1280 ≈ 12.5 frames/sec)
                        rospy.logdebug(f"[OpenWakeWord] 目前分數: {score:.4f}")
                        
                    if score >= self._threshold and (current_time - last_trigger_time) > cooldown_seconds:
                        rospy.loginfo(f"[OpenWakeWord] 🚀 [喚醒成功] 阿布聽到你了！ (瞬間峰值: {score:.3f})")
                        last_trigger_time = current_time
                        
                        # ⚠️ 關鍵：在此處主動關閉目前的麥克風串流
                        # 讓後續的 VADRecorder 可以順利接管麥克風，避免 Device unavailable
                        if stream is not None:
                            stream.stop_stream()
                            stream.close()
                            stream = None
                        
                        # 完全終止 pyaudio 實例以釋放 ALSA 鎖
                        if self._pa is not None:
                            self._pa.terminate()
                            self._pa = None
                        
                        # 讓作業系統有時間切換 ALSA 資源
                        time.sleep(0.3)
                            
                        # 呼叫外層的回呼函數 (會阻塞直到 VAD 錄音+處理結束)
                        self._on_wake()
                        
                        # VAD 結束後，重新建立 PyAudio 實例
                        self._pa = pyaudio.PyAudio()
                        
                        # 跳出內層迴圈，讓外層 while self._running 重新打開麥克風
                        break
            
            except Exception as e:
                # 錄音設備開啟失敗或中途被搶斷，稍微暫停後重試
                if self._running:
                    rospy.logdebug(f"[OpenWakeWord] 錄音串流中斷/無法開啟，等待重試... ({e})")
                    time.sleep(0.5)
            finally:
                if stream is not None:
                    stream.stop_stream()
                    stream.close()
