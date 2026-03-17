#!/usr/bin/env python3
"""
wake_word_detector.py
=====================
Porcupine 喚醒詞偵測模組。

職責（單一功能）：
    持續從麥克風讀取音訊，偵測到指定喚醒詞（如「阿布」）時呼叫回呼函數。
    不做錄音、不做語音轉文字，只負責喚醒偵測。
"""
import struct
import threading
from typing import Callable, Optional


class WakeWordDetector:
    """
    使用 Porcupine 進行喚醒詞偵測。

    用法:
        def on_wake():
            print("偵測到阿布！")

        detector = WakeWordDetector(
            access_key   = "YOUR_KEY",
            keyword_path = "/path/to/abu.ppn",
            sensitivity  = 0.7,
            on_wake      = on_wake,
        )
        detector.start()   # 背景執行緒
        ...
        detector.stop()
    """

    def __init__(self,
                 access_key:   str,
                 keyword_path: str,
                 sensitivity:  float,
                 on_wake:      Callable[[], None],
                 sample_rate:  int = 16000):
        """
        參數:
            access_key   : Picovoice Access Key
            keyword_path : .ppn 自定義關鍵詞檔案路徑
            sensitivity  : 偵測靈敏度（0.0 ~ 1.0）
            on_wake      : 偵測到喚醒詞時呼叫的 callback（無參數）
            sample_rate  : 麥克風取樣率（Porcupine 需要 16000 Hz）
        """
        import pvporcupine
        import pyaudio

        self._porcupine = pvporcupine.create(
            access_key   = access_key,
            keyword_paths = [keyword_path],
            sensitivities = [sensitivity],
        )
        self._pa = pyaudio.PyAudio()
        self._stream = self._pa.open(
            rate             = self._porcupine.sample_rate,
            channels         = 1,
            format           = pyaudio.paInt16,
            input            = True,
            frames_per_buffer = self._porcupine.frame_length,
        )

        self._on_wake  = on_wake
        self._running  = False
        self._thread: Optional[threading.Thread] = None

    # ── 公開介面 ──────────────────────────────────────────────────────────

    def start(self) -> None:
        """啟動背景監聽執行緒。"""
        self._running = True
        self._thread  = threading.Thread(
            target=self._listen_loop, daemon=True, name="WakeWordDetector")
        self._thread.start()

    def stop(self) -> None:
        """停止監聽並釋放資源。"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
        self._stream.stop_stream()
        self._stream.close()
        self._pa.terminate()
        self._porcupine.delete()

    # ── 私有方法 ──────────────────────────────────────────────────────────

    def _listen_loop(self) -> None:
        """持續讀取麥克風並交給 Porcupine 判斷。"""
        frame_len = self._porcupine.frame_length
        while self._running:
            try:
                raw = self._stream.read(frame_len, exception_on_overflow=False)
                pcm = struct.unpack_from(f"{frame_len}h", raw)
                result = self._porcupine.process(pcm)
                if result >= 0:
                    # result == keyword index（我們只有一個，所以 >=0 即觸發）
                    self._on_wake()
            except Exception:
                if self._running:
                    raise
