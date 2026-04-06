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
import audioop
from typing import Callable, Optional

class OpenWakeWordDetector:
    _FIXED_CAPTURE_RATE = 48000

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
        self._capture_rate = self._sample_rate
        self._resample_state = None

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
        self._enabled  = True
        self._cooldown_seconds = 2.0
        self._post_process_block_seconds = 2.5
        self._armed = True
        self._rearm_low_streak = 0
        self._rearm_required_low_frames = 8
        self._rearm_threshold_ratio = 0.4
        self._debug_log_interval_sec = 1.0
        self._thread: Optional[threading.Thread] = None

    def set_enabled(self, enabled: bool) -> None:
        """啟用/停用喚醒詞偵測（停用時不做預測）。"""
        self._enabled = bool(enabled)

    def _open_input_stream(self):
        """開啟輸入串流：固定使用 48kHz 擷取，再重採樣到 16kHz。"""
        import rospy

        candidates = []
        if self._input_device_index is not None:
            candidates.append(self._input_device_index)
        candidates.append(None)

        tried = set()
        last_exc = None
        for device_index in candidates:
            key = device_index
            if key in tried:
                continue
            tried.add(key)

            try:
                stream = self._pa.open(
                    rate              = self._FIXED_CAPTURE_RATE,
                    channels          = 1,
                    format            = self._pa.get_format_from_width(2),
                    input             = True,
                    input_device_index = device_index,
                    frames_per_buffer = max(1, int(self._FIXED_CAPTURE_RATE * (self._chunk_size / float(self._sample_rate)))),
                )
                self._capture_rate = self._FIXED_CAPTURE_RATE
                self._resample_state = None
                if self._capture_rate != self._sample_rate:
                    rospy.loginfo(f"[OpenWakeWord] 固定採樣 {self._capture_rate}Hz，並即時重採樣到 {self._sample_rate}Hz。")
                return stream
            except Exception as e:
                last_exc = e

        raise last_exc if last_exc else RuntimeError("無法開啟錄音輸入串流")

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
        
        last_trigger_time = 0.0
        hit_streak = 0

        rospy.loginfo(f"[OpenWakeWord] 🎤 開始監聽麥克風 (Target={self._keyword}, Threshold={self._threshold})")
        
        frame_count = 0
        last_debug_log_time = 0.0
        while self._running:
            if not self._enabled:
                time.sleep(0.02)
                continue

            stream = None
            try:
                # 確保 self._pa 存在
                if self._pa is None:
                    self._pa = pyaudio.PyAudio()

                stream = self._open_input_stream()
                capture_chunk = max(1, int(self._capture_rate * (self._chunk_size / float(self._sample_rate))))
                
                while self._running:
                    # 讀取音訊資料 (16-bit PCM)，如果 overflow 發生我們直接忽略並繼續
                    raw = stream.read(capture_chunk, exception_on_overflow=False)

                    if self._capture_rate != self._sample_rate:
                        raw, self._resample_state = audioop.ratecv(
                            raw,
                            2,
                            1,
                            self._capture_rate,
                            self._sample_rate,
                            self._resample_state,
                        )

                    pcm = np.frombuffer(raw, dtype=np.int16)
                    
                    # 偵測幾乎無輸入的音量（可能是裝置暫時無資料）
                    if np.abs(pcm).mean() < 2:
                        # 假如有別人(VADRecorder)正在搶 Mic，音量可能變成接近 0
                        # 我們就當成沒收到聲音處理，不預測，降低 CPU 使用率
                        time.sleep(0.01)
                        continue
                        
                    # 進行預測
                    prediction = self._model.predict(pcm)
                    
                    # 取得該關鍵字的最新信心分數
                    score = prediction.get(self._keyword, 0.0)
                    current_time = time.time()

                    if score >= self._threshold:
                        hit_streak += 1
                    else:
                        hit_streak = 0

                    # 觸發後需先「重新武裝」：觀察到一段連續低分才允許下一次觸發
                    if not self._armed:
                        if score < (self._threshold * self._rearm_threshold_ratio):
                            self._rearm_low_streak += 1
                        else:
                            self._rearm_low_streak = 0

                        if self._rearm_low_streak >= self._rearm_required_low_frames:
                            self._armed = True
                            self._rearm_low_streak = 0

                        continue
                    
                    frame_count += 1
                    if current_time - last_debug_log_time >= self._debug_log_interval_sec:
                        cooldown_left = max(0.0, (last_trigger_time + self._cooldown_seconds) - current_time)
                        rospy.logdebug(
                            f"[OpenWakeWord] 分數={score:.4f}, threshold={self._threshold:.2f}, "
                            f"armed={self._armed}, enabled={self._enabled}, cooldown_left={cooldown_left:.2f}s"
                        )
                        last_debug_log_time = current_time
                        
                    if (
                        score >= self._threshold
                        and (current_time - last_trigger_time) > self._cooldown_seconds
                    ):
                        rospy.loginfo(f"[OpenWakeWord] 🚀 [喚醒成功] 阿布聽到你了！ (瞬間峰值: {score:.3f})")
                        last_trigger_time = current_time
                        hit_streak = 0
                        self._armed = False
                        self._rearm_low_streak = 0
                        
                        # ⚠️ 關鍵：在此處主動關閉目前的麥克風串流
                        # 讓後續的 VADRecorder 可以順利接管麥克風，避免 Device unavailable
                        if stream is not None:
                            stream.stop_stream()
                            stream.close()
                            stream = None

                        # 縮短交接延遲：stream 關閉即可釋放輸入，僅保留極短等待
                        time.sleep(0.05)

                        # 喚醒後先暫停關鍵字偵測，待 VAD + Whisper 完成再恢復
                        self.set_enabled(False)
                        try:
                            # 呼叫外層的回呼函數 (會阻塞直到 VAD 錄音+處理結束)
                            self._on_wake()
                        finally:
                            # 任務完成後保留一段抑制時間，避免尾音/回授立即重觸發
                            last_trigger_time = time.time() + self._post_process_block_seconds
                            self.set_enabled(True)
                        
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
