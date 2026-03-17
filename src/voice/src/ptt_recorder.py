#!/usr/bin/env python3
"""
ptt_recorder.py
===============
Push-to-Talk 錄音模組。

職責（單一功能）：
    提供「按下開始錄音、放開停止錄音」的 PTT 錄音功能，
    回傳 WAV bytes 供 Whisper API 使用。
    不做喚醒詞偵測、不做 VAD、不做語音轉文字。

    與 vad_recorder.py 的差異：
        vad_recorder : VAD 自動偵測靜音結束
        ptt_recorder : 由外部控制（鍵盤/按鈕）決定開始與結束
"""
import io
import wave
import threading
from typing import Optional


class PTTRecorder:
    """
    Push-to-Talk 錄音器。

    用法:
        recorder = PTTRecorder(sample_rate=16000)
        recorder.start_recording()   # 按下鍵時呼叫
        ...
        wav_bytes = recorder.stop_recording()  # 放開鍵時呼叫
    """

    def __init__(self,
                 sample_rate: int = 16000,
                 chunk_size:  int = 1024):
        """
        參數:
            sample_rate : 取樣率（Hz），Whisper 需要 16000
            chunk_size  : 每次讀取的 PCM 幀數
        """
        import pyaudio
        self._pa          = pyaudio.PyAudio()
        self._format      = pyaudio.paInt16
        self._sample_rate = sample_rate   # 目標採樣率（Whisper 使用）
        self._chunk_size  = chunk_size

        self._frames:  list        = []
        self._stream               = None
        self._recording: bool      = False
        self._lock = threading.Lock()

        # 自動偵測 USB 麥克風，優先使用（名稱含 USB 或 usb）
        self._input_device_index, self._hw_sample_rate = self._find_usb_mic(sample_rate)

    @staticmethod
    def _find_usb_mic(target_rate: int):
        """
        搜尋名稱含 'USB' 的輸入設備。
        回傳 (device_index, actual_hw_rate)：
            - 找到 USB 麥克風 → 回傳其 index 與硬體原生採樣率
            - 找不到          → 回傳 (None, target_rate) 使用系統預設
        """
        import pyaudio
        pa = pyaudio.PyAudio()
        found_id   = None
        found_rate = target_rate
        for i in range(pa.get_device_count()):
            info = pa.get_device_info_by_index(i)
            if info["maxInputChannels"] > 0 and "usb" in info["name"].lower():
                found_id   = i
                found_rate = int(info["defaultSampleRate"])
                break
        pa.terminate()
        if found_id is not None:
            print(f"[PTTRecorder] 偵測到 USB 麥克風，設備 ID [{found_id}]，"
                  f"硬體採樣率 {found_rate}Hz → 錄音後重採樣至 {target_rate}Hz")
        else:
            print("[PTTRecorder] 未偵測到 USB 麥克風，使用系統預設輸入設備")
        return found_id, found_rate

    # ── 公開介面 ──────────────────────────────────────────────────────────

    def start_recording(self) -> None:
        """開始錄音（按下鍵時呼叫）。"""
        import pyaudio
        with self._lock:
            if self._recording:
                return
            self._frames    = []
            self._recording = True
            self._stream    = self._pa.open(
                format           = self._format,
                channels         = 1,
                rate             = self._hw_sample_rate,   # 硬體實際支援的採樣率
                input            = True,
                frames_per_buffer = self._chunk_size,
                input_device_index = self._input_device_index,
            )

        # 在背景執行緒連續讀取音訊
        self._record_thread = threading.Thread(
            target=self._capture_loop, daemon=True)
        self._record_thread.start()

    def stop_recording(self) -> Optional[bytes]:
        """
        停止錄音（放開鍵時呼叫）。

        回傳:
            WAV 格式 bytes；若錄音過短（< 0.3s）則回傳 None。
        """
        with self._lock:
            self._recording = False

        if hasattr(self, "_record_thread"):
            self._record_thread.join(timeout=2.0)

        if self._stream:
            self._stream.stop_stream()
            self._stream.close()
            self._stream = None

        min_chunks = int(self._sample_rate * 0.3 / self._chunk_size)
        if len(self._frames) < min_chunks:
            return None

        return self._to_wav_bytes(self._frames)

    def close(self) -> None:
        """釋放 PyAudio 資源。"""
        self._pa.terminate()

    # ── 私有方法 ──────────────────────────────────────────────────────────

    def _capture_loop(self) -> None:
        """背景執行緒：錄音中持續讀取 PCM。"""
        while self._recording and self._stream:
            try:
                data = self._stream.read(
                    self._chunk_size, exception_on_overflow=False)
                with self._lock:
                    if self._recording:
                        self._frames.append(data)
            except Exception:
                break

    def _to_wav_bytes(self, frames: list) -> bytes:
        """PCM frames → WAV bytes（若硬體採樣率 ≠ 目標採樣率，自動重採樣）。"""
        import pyaudio
        import audioop
        raw = b"".join(frames)

        # 重採樣：硬體採樣率 → 目標採樣率（Whisper 需要 16000Hz）
        if self._hw_sample_rate != self._sample_rate:
            raw, _ = audioop.ratecv(
                raw, 2, 1,
                self._hw_sample_rate,
                self._sample_rate,
                None
            )

        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(self._pa.get_sample_size(self._format))
            wf.setframerate(self._sample_rate)
            wf.writeframes(raw)
        return buf.getvalue()
