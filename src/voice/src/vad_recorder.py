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
import audioop
import os
from typing import Optional


class VADRecorder:
    _FIXED_CAPTURE_RATE = 48000
    _DEBUG_DUMP_DIR = "/tmp/voice_debug_wav"

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
                 max_record_sec:      float = 15.0,
                 no_speech_timeout_sec: float = 5.0):
        """
        參數:
            sample_rate          : 取樣率（Hz），需與麥克風串流一致
            chunk_ms             : 每幀長度（ms），影響 VAD 精度
            vad_mode             : webrtcvad 積極度（3 最積極過濾噪音）
            silence_duration_sec : 靜音超過幾秒視為說完話
            max_record_sec       : 最長錄音時間（避免無限錄音）
            no_speech_timeout_sec: 開始錄音後，若超過此秒數仍未偵測到語音則放棄
        """
        import webrtcvad
        import pyaudio

        self._sample_rate   = sample_rate
        self._chunk_ms      = chunk_ms
        self._chunk_size    = int(sample_rate * chunk_ms / 1000)  # samples per frame
        self._silence_sec   = silence_duration_sec
        self._max_sec       = max_record_sec
        self._no_speech_timeout_sec = no_speech_timeout_sec

        self._vad = webrtcvad.Vad(vad_mode)
        self._pa  = pyaudio.PyAudio()

        # 自動偵測 USB 麥克風，優先使用（名稱含 USB 或 usb）
        self._input_device_index = self._find_usb_mic()

    def _open_input_stream(self):
        """開啟錄音串流：固定使用 48kHz 擷取，再重採樣到 16kHz。"""
        import pyaudio

        if self._input_device_index is None:
            raise RuntimeError("[VADRecorder] 找不到 USB 麥克風，已停用系統預設麥克風 fallback。")

        candidates = [self._input_device_index]

        last_exc = None
        for retry_round in range(3):
            tried = set()
            for device_index in candidates:
                key = device_index
                if key in tried:
                    continue
                tried.add(key)

                try:
                    info = self._pa.get_device_info_by_index(device_index)
                    print(f"[VADRecorder] 使用 USB 麥克風: id={device_index}, name={info.get('name')}")
                    stream = self._pa.open(
                        rate              = self._FIXED_CAPTURE_RATE,
                        channels          = 1,
                        format            = pyaudio.paInt16,
                        input             = True,
                        input_device_index = device_index,
                        frames_per_buffer = max(1, int(self._FIXED_CAPTURE_RATE * self._chunk_ms / 1000)),
                    )
                    return stream, self._FIXED_CAPTURE_RATE
                except Exception as e:
                    last_exc = e

            time.sleep(0.25 * (retry_round + 1))

        raise last_exc if last_exc else RuntimeError("無法開啟錄音輸入串流")

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
        stream, capture_rate = self._open_input_stream()
        capture_chunk = max(1, int(capture_rate * self._chunk_ms / 1000))
        resample_state = None
        if capture_rate != self._sample_rate:
            print(f"[VADRecorder] 固定採樣 {capture_rate}Hz，並即時重採樣到 {self._sample_rate}Hz。")

        frames        = []
        silence_start = None
        start_time    = time.time()
        speech_started = False
        speech_frames = 0

        try:
            while True:
                elapsed = time.time() - start_time
                if elapsed > self._max_sec:
                    break

                if (not speech_started) and elapsed >= self._no_speech_timeout_sec:
                    print(f"[VADRecorder] {self._no_speech_timeout_sec:.1f}s 內未偵測到語音，放棄本次錄音。")
                    break

                raw = stream.read(capture_chunk, exception_on_overflow=False)

                if capture_rate != self._sample_rate:
                    raw, resample_state = audioop.ratecv(
                        raw,
                        2,
                        1,
                        capture_rate,
                        self._sample_rate,
                        resample_state,
                    )

                is_speech = self._vad.is_speech(raw, self._sample_rate)
                frames.append(raw)

                if is_speech:
                    speech_started = True
                    speech_frames += 1
                    silence_start = None  # 有說話，重置靜音計時
                else:
                    # 尚未開始說話前，不要用靜音計時提前結束錄音
                    if not speech_started:
                        continue

                    if silence_start is None:
                        silence_start = time.time()
                    elif time.time() - silence_start >= self._silence_sec:
                        break
        finally:
            stream.stop_stream()
            stream.close()

        # 除錯用：每次錄音都先落地，方便直接聽檔確認麥克風是否有收到聲音
        debug_wav_path = self._dump_debug_wav(frames)
        if debug_wav_path:
            print(f"[VADRecorder] 已儲存錄音除錯檔：{debug_wav_path}")

        # 錄音過短則視為無效
        if not speech_started or speech_frames < 3:
            print("[VADRecorder] 未偵測到足夠語音內容，忽略本次錄音。")
            return None

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

    def _dump_debug_wav(self, frames: list) -> Optional[str]:
        """將本次錄音存成 wav 檔，便於人工聆聽除錯。"""
        if not frames:
            return None

        try:
            os.makedirs(self._DEBUG_DUMP_DIR, exist_ok=True)
            ts = int(time.time() * 1000)
            path = os.path.join(self._DEBUG_DUMP_DIR, f"capture_{ts}.wav")
            with open(path, "wb") as f:
                f.write(self._to_wav_bytes(frames))
            return path
        except Exception as e:
            print(f"[VADRecorder] 儲存除錯音檔失敗：{e}")
            return None
