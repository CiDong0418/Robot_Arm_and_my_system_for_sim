#!/usr/bin/env python3
"""
vad_recorder.py
===============
VAD（語音活動偵測）錄音模組。

職責（單一功能）：
    在被呼叫後開始從麥克風錄音，使用 webrtcvad 判斷說話是否結束
    （靜音持續超過門檻秒數），回傳完整的 WAV bytes。
    不做喚醒詞偵測，不做語音轉文字。
"""
import io
import wave
import time
from typing import Optional


class VADRecorder:
    """
    基於 webrtcvad 的語音活動偵測錄音器。

    流程：
        record() 被呼叫後立即開始收音，
        當靜音時間超過 silence_duration_sec 或超過 max_record_sec 則停止，
        回傳 WAV 格式的 bytes（可直接送 Whisper API）。

    用法:
        recorder = VADRecorder(sample_rate=16000)
        wav_bytes = recorder.record()
        # wav_bytes: WAV 格式 bytes
    """

    def __init__(self,
                 sample_rate:         int   = 16000,
                 chunk_ms:            int   = 30,     # ms，webrtcvad 支援 10/20/30
                 vad_mode:            int   = 3,      # 0(寬鬆)~3(嚴格)
                 silence_duration_sec: float = 1.5,
                 max_record_sec:      float = 15.0):
        """
        參數:
            sample_rate          : 取樣率（Hz），需與麥克風串流一致
            chunk_ms             : 每幀長度（ms），影響 VAD 精度
            vad_mode             : webrtcvad 積極度（3 最積極過濾噪音）
            silence_duration_sec : 靜音超過幾秒視為說完話
            max_record_sec       : 最長錄音時間（避免無限錄音）
        """
        import webrtcvad
        import pyaudio

        self._sample_rate   = sample_rate
        self._chunk_ms      = chunk_ms
        self._chunk_size    = int(sample_rate * chunk_ms / 1000)  # samples per frame
        self._silence_sec   = silence_duration_sec
        self._max_sec       = max_record_sec

        self._vad = webrtcvad.Vad(vad_mode)
        self._pa  = pyaudio.PyAudio()

        # 自動偵測 USB 麥克風，優先使用（名稱含 USB 或 usb）
        self._input_device_index = self._find_usb_mic()

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
            print(f"[VADRecorder] 偵測到 USB 麥克風，使用設備 ID [{found}]")
        else:
            print("[VADRecorder] 未偵測到 USB 麥克風，使用系統預設輸入設備")
        return found

    # ── 公開介面 ──────────────────────────────────────────────────────────

    def record(self) -> Optional[bytes]:
        """
        開始錄音，VAD 判斷說話結束後停止。

        回傳:
            WAV 格式 bytes；若錄音長度過短（< 0.3s）則回傳 None。
        """
        import pyaudio

        try:
            stream = self._pa.open(
                rate             = self._sample_rate,
                channels         = 1,
                format           = pyaudio.paInt16,
                input            = True,
                frames_per_buffer = self._chunk_size,
                # input_device_index = self._input_device_index,
            )
        except Exception as e:
            if self._input_device_index is not None:
                print(f"[VADRecorder] 無法以 16000Hz 打開 USB 麥克風 (ID={self._input_device_index})，可能是不支援該取樣率: {e}")
                print("[VADRecorder] 嘗試降級使用系統預設錄音設備 (通常支援自動重採樣)...")
                stream = self._pa.open(
                    rate             = self._sample_rate,
                    channels         = 1,
                    format           = pyaudio.paInt16,
                    input            = True,
                    frames_per_buffer = self._chunk_size,
                )
            else:
                raise

        frames        = []
        silence_start = None
        start_time    = time.time()

        try:
            while True:
                elapsed = time.time() - start_time
                if elapsed > self._max_sec:
                    break

                raw = stream.read(self._chunk_size, exception_on_overflow=False)
                is_speech = self._vad.is_speech(raw, self._sample_rate)
                frames.append(raw)

                if not is_speech:
                    if silence_start is None:
                        silence_start = time.time()
                    elif time.time() - silence_start >= self._silence_sec:
                        break
                else:
                    silence_start = None  # 有說話，重置靜音計時
        finally:
            stream.stop_stream()
            stream.close()

        # 錄音過短則視為無效
        min_frames = int(self._sample_rate * 0.3 / self._chunk_size)
        if len(frames) < min_frames:
            return None

        return self._to_wav_bytes(frames)

    def close(self) -> None:
        """釋放 PyAudio 資源。"""
        self._pa.terminate()

    # ── 私有方法 ──────────────────────────────────────────────────────────

    def _to_wav_bytes(self, frames: list) -> bytes:
        """將 PCM frames 轉為標準 WAV bytes。"""
        import pyaudio
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(self._pa.get_sample_size(pyaudio.paInt16))
            wf.setframerate(self._sample_rate)
            wf.writeframes(b"".join(frames))
        return buf.getvalue()
