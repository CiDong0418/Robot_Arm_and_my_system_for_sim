#!/usr/bin/env python3
"""
whisper_transcriber.py
======================
OpenAI Whisper API 語音轉文字模組。

職責（單一功能）：
    接收 WAV bytes，呼叫 OpenAI Whisper API，回傳轉錄文字。
    不做錄音、不做喚醒偵測。

    API Key 讀取順序：
        1. 建構子傳入的 api_key 參數
        2. 同目錄 .env 檔案中的 OPENAI_API_KEY
        3. 環境變數 OPENAI_API_KEY
"""
import io
import os
from typing import Optional


def _load_api_key_from_env(env_path: str) -> str:
    """從 .env 檔案讀取 OPENAI_API_KEY。"""
    if os.path.isfile(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line.startswith("OPENAI_API_KEY="):
                    return line.split("=", 1)[1].strip()
    return os.environ.get("OPENAI_API_KEY", "")


class WhisperTranscriber:
    """
    OpenAI Whisper API 封裝器。

    用法:
        transcriber = WhisperTranscriber(api_key="sk-...", language="zh")
        text = transcriber.transcribe(wav_bytes)
        print(text)   # "幫我拿杯子"
    """

    def __init__(self,
                 api_key:  str = "",
                 model:    str = "whisper-1",
                 language: str = "zh"):
        """
        參數:
            api_key  : OpenAI API Key；留空時自動從同目錄 .env 讀取
            model    : Whisper 模型名稱（預設 whisper-1）
            language : 語言代碼（zh=中文）
        """
        from openai import OpenAI

        # 若未傳入 api_key，從 .env 讀取
        if not api_key or api_key in ("from_env", "sk-..."):
            _env_path = os.path.join(os.path.dirname(__file__), ".env")
            api_key   = _load_api_key_from_env(_env_path)

        if not api_key:
            raise ValueError("找不到 OpenAI API Key，請在 .env 填入 OPENAI_API_KEY。")

        self._client   = OpenAI(api_key=api_key)
        self._model    = model
        self._language = language

    # ── 公開介面 ──────────────────────────────────────────────────────────

    def transcribe(self, wav_bytes: bytes) -> Optional[str]:
        """
        將 WAV bytes 送到 Whisper API 進行語音轉文字。

        參數:
            wav_bytes: WAV 格式的音訊 bytes（由 VADRecorder.record() 產生）

        回傳:
            轉錄文字 str；若 API 回應為空或發生錯誤則回傳 None。
        """
        if not wav_bytes:
            return None

        # 包裝成 file-like object 並命名為 .wav（API 需要副檔名辨識格式）
        audio_file = io.BytesIO(wav_bytes)
        audio_file.name = "audio.wav"

        try:
            response = self._client.audio.transcriptions.create(
                model    = self._model,
                file     = audio_file,
                language = self._language,
            )
            text = response.text.strip()
            return text if text else None
        except Exception as e:
            raise RuntimeError(f"Whisper API 呼叫失敗：{e}") from e
