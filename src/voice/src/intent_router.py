#!/usr/bin/env python3
"""
intent_router.py
================
判斷語句是否為機器人任務，並產生可播報的口語回覆。
"""
import json
import os
from typing import Dict


def _load_api_key_from_env(env_path: str) -> str:
    if os.path.isfile(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line.startswith("OPENAI_API_KEY="):
                    return line.split("=", 1)[1].strip()
    return os.environ.get("OPENAI_API_KEY", "")


class IntentRouter:
    """語意路由：回傳 is_task 與 reply。"""

    _SYSTEM_PROMPT = """
你是家用機器人的語意路由器。
你會收到一段中文語句，請輸出 JSON：
{
  "is_task": true/false,
  "reply": "給使用者的一句口語回覆（繁體中文）"
}

判斷規則：
- is_task=true：使用者要機器人執行實體任務（拿、放、移動、倒、開關、送、清理、操作物品等）
- is_task=false：一般聊天、問候、閒聊、知識問答，不需機器人動作

reply 規則：
- 繁體中文，1 句，簡短自然，可直接給 TTS 播放
- 若 is_task=true：回覆「收到，會執行…」類型
- 若 is_task=false：回覆一般聊天內容

只輸出合法 JSON，不要 markdown。
""".strip()

    def __init__(self, api_key: str = "", model: str = "gpt-4o-mini"):
        from openai import OpenAI

        if not api_key or api_key in ("from_env", "sk-..."):
            env_path = os.path.join(os.path.dirname(__file__), ".env")
            api_key = _load_api_key_from_env(env_path)

        if not api_key:
            raise ValueError("找不到 OpenAI API Key，請在 .env 填入 OPENAI_API_KEY。")

        self._client = OpenAI(api_key=api_key)
        self._model = model

    def route(self, text: str) -> Dict[str, object]:
        text = (text or "").strip()
        if not text:
            return {"is_task": False, "reply": "我剛剛沒有聽清楚，可以再說一次嗎？"}

        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": self._SYSTEM_PROMPT},
                    {"role": "user", "content": text},
                ],
                temperature=0,
                response_format={"type": "json_object"},
            )

            content = response.choices[0].message.content
            data = json.loads(content)

            is_task = bool(data.get("is_task", False))
            reply = str(data.get("reply", "")).strip()
            if not reply:
                reply = "收到，我來處理。" if is_task else "好的。"

            return {"is_task": is_task, "reply": reply}

        except Exception:
            # API 失敗時保守回退：任務語氣視為任務，其他當聊天
            task_keywords = ["幫我", "請", "拿", "放", "移", "倒", "送", "打開", "關", "清理", "操作"]
            is_task = any(k in text for k in task_keywords)
            reply = "收到，我會幫你執行這個任務。" if is_task else "好的，我知道了。"
            return {"is_task": is_task, "reply": reply}
