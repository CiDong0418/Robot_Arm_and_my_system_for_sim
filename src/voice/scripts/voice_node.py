#!/usr/bin/env python3
"""
voice_node.py
============= 111
語音辨識 ROS 節點。

流程：
    1. Porcupine 背景監聽麥克風，偵測到喚醒詞「阿布」
    2. 發布 status = "recording"，開始 VAD 錄音
    3. 偵測到靜音（說話結束）後停止錄音，發布 status = "processing"
    4. 將錄音送 OpenAI Whisper API 轉文字
    5. 發布轉錄結果到 /voice/transcript，status 回到 "idle"

發布:
    /user_command      (std_msgs/String)  — 語音轉錄出來的最終指令 (送給大腦)
    /voice/status      (std_msgs/String)  — 目前狀態
        idle        : 等待喚醒詞 1
        woke        : 偵測到喚醒詞，準備錄音
        recording   : 錄音中
        processing  : 呼叫 Whisper API 中
        error       : 發生錯誤（附說明）
"""
import os
import sys
import yaml
import threading

import rospy
from std_msgs.msg import String

# ── src/ 模組路徑 ──
_PKG_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SRC_DIR  = os.path.join(_PKG_DIR, "src")
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)

from open_wake_word_detector import OpenWakeWordDetector
from vad_recorder        import VADRecorder
from whisper_transcriber import WhisperTranscriber
from intent_router       import IntentRouter


# ──────────────────────────── 設定讀取 ────────────────────────────────────
def _load_config() -> dict:
    yaml_path = os.path.join(_PKG_DIR, "config", "config.yaml")
    if not os.path.isfile(yaml_path):
        rospy.logfatal(f"[voice] 找不到 config.yaml：{yaml_path}")
        raise FileNotFoundError(yaml_path)
    with open(yaml_path, "r") as f:
        return yaml.safe_load(f)


# ──────────────────────────── ROS 節點 ────────────────────────────────────
class VoiceNode:
    """語音辨識 ROS 節點（Porcupine → VAD → Whisper）。"""

    def __init__(self):
        rospy.init_node("voice_node", anonymous=False, log_level=rospy.DEBUG)
        cfg = _load_config()

        oai_cfg  = cfg["openai"]
        porc_cfg = cfg["porcupine"]
        aud_cfg  = cfg["audio"]

        # ── 確認關鍵設定已填入 ──
        keyword_path_cfg = porc_cfg.get("keyword_path", "")
        if not keyword_path_cfg or not keyword_path_cfg.endswith(".onnx"):
            # 預設使用 src 目錄下的 abu.onnx
            keyword_path_cfg = os.path.join(_SRC_DIR, "abu.onnx")
            
        threshold = float(porc_cfg.get("sensitivity", 0.5))

        # ── Publishers ──
        self._pub_transcript = rospy.Publisher(
            "/user_command", String, queue_size=10)
        self._pub_reply = rospy.Publisher(
            "/assistant_reply", String, queue_size=10)
        self._pub_status = rospy.Publisher(
            "/voice/status", String, queue_size=5)

        # ── 初始化各模組 ──
        rospy.loginfo("[voice] 初始化 VAD 錄音器...")
        self._recorder = VADRecorder(
            sample_rate          = aud_cfg["sample_rate"],
            chunk_ms             = int(aud_cfg["chunk_size"] * 1000 / aud_cfg["sample_rate"]),
            vad_mode             = aud_cfg["vad_mode"],
            silence_duration_sec = aud_cfg["silence_duration_sec"],
            max_record_sec       = aud_cfg["max_record_sec"],
            no_speech_timeout_sec = float(aud_cfg.get("no_speech_timeout_sec", 5.0)),
        )

        rospy.loginfo("[voice] 初始化 Whisper 轉錄器...")
        self._transcriber = WhisperTranscriber(
            model    = oai_cfg["model"],
            language = oai_cfg["language"],
        )  # api_key 自動從 src/.env 的 OPENAI_API_KEY 讀取

        router_model = oai_cfg.get("intent_model", "gpt-4o-mini")
        rospy.loginfo("[voice] 初始化語意路由器...")
        self._intent_router = IntentRouter(model=router_model)

        # 防止喚醒詞重複觸發的鎖
        self._processing_lock = threading.Lock()

        rospy.loginfo("[voice] 初始化 OpenWakeWord 喚醒詞偵測器...")
        self._wake_detector = OpenWakeWordDetector(
            keyword_path = keyword_path_cfg,
            on_wake      = self._on_wake,
            threshold    = threshold,
            sample_rate  = aud_cfg["sample_rate"],
        )
        self._wake_detector.start()

        self._publish_status("idle")
        rospy.loginfo("[voice] 節點就緒。說「阿布」來啟動語音輸入。")

    # ── 喚醒詞 Callback ───────────────────────────────────────────────────

    def _on_wake(self) -> None:
        """
        偵測到喚醒詞時觸發。
        用 lock 確保同時只有一個辨識流程在執行。
        """
        if not self._processing_lock.acquire(blocking=False):
            rospy.logwarn("[voice] 正在處理中，忽略此次喚醒。")
            return

        # 在同一執行緒執行錄音+辨識，避免 OpenWakeWord 與 VAD 同時搶麥克風
        self._record_and_transcribe()

    # ── 錄音 + 辨識流程 ──────────────────────────────────────────────────

    def _record_and_transcribe(self) -> None:
        """喚醒後執行：錄音 → Whisper → 發布結果。"""
        try:
            self._wake_detector.set_enabled(False)
            rospy.loginfo("[voice] ✅ 偵測到「阿布」！開始錄音...")
            self._publish_status("woke")

            self._publish_status("recording")
            rospy.loginfo("[voice] 🎙️  錄音中，請說話...")

            wav_bytes = self._recorder.record()

            if wav_bytes is None:
                rospy.logwarn("[voice] 錄音過短或無效，忽略。")
                self._publish_status("idle")
                return

            rospy.loginfo("[voice] 🔄  錄音完成，送 Whisper API 轉錄...")
            self._publish_status("processing")

            text = self._transcriber.transcribe(wav_bytes)

            if text and not self._is_invalid_transcript(text):
                rospy.loginfo(f"[voice] 📝  轉錄結果：「{text}」")
                route = self._intent_router.route(text)
                is_task = bool(route.get("is_task", False))
                reply = str(route.get("reply", "")).strip()

                if reply:
                    self._publish_reply(reply)

                if is_task:
                    self._publish_transcript(text)
                else:
                    rospy.loginfo("[voice] 判定為一般聊天，不送入 /user_command。")

                self._publish_status("idle")
            else:
                rospy.logwarn("[voice] 本次無有效轉錄文字（空字串或誤轉錄樣板）。")
                print("[voice][transcript] <NO_VALID_TEXT>", flush=True)
                self._publish_status("idle")

        except Exception as e:
            rospy.logerr(f"[voice] 錯誤：{e}")
            self._publish_status(f"error: {e}")
        finally:
            self._wake_detector.set_enabled(True)
            self._processing_lock.release()

    # ── 發布輔助方法 ──────────────────────────────────────────────────────

    def _publish_transcript(self, text: str) -> None:
        msg = String()
        # ROS 的 std_msgs.msg.String 在 Python3 中預設接收字串
        # 但為了確保中文發送正確不被轉譯為 ASCII escape，我們明確宣告字串
        msg.data = text
        self._pub_transcript.publish(msg)
        print(f"[voice][transcript] {text}", flush=True)

    def _publish_status(self, status: str) -> None:
        msg = String()
        msg.data = status
        self._pub_status.publish(msg)

    def _publish_reply(self, text: str) -> None:
        msg = String()
        msg.data = text
        self._pub_reply.publish(msg)
        print(f"[voice][reply] {text}", flush=True)

    @staticmethod
    def _is_invalid_transcript(text: str) -> bool:
        """過濾常見 Whisper 靜音誤轉錄樣板。"""
        normalized = (
            text.strip()
            .lower()
            .replace(" ", "")
            .replace("。", "")
            .replace("，", "")
            .replace(".", "")
            .replace(",", "")
        )

        known_bad = {
            "由amaraorg社群提供的字幕",
            "字幕由amaraorg社群提供",
            "字幕由amaraorg社区提供",
            "由amaraorg社区提供字幕",
        }
        return normalized in known_bad

    # ── 清理 ──────────────────────────────────────────────────────────────

    def shutdown(self) -> None:
        rospy.loginfo("[voice] 節點關閉。")
        self._wake_detector.stop()
        self._recorder.close()


# ──────────────────────────── 程式入口 ────────────────────────────────────
if __name__ == "__main__":
    node = VoiceNode()
    rospy.on_shutdown(node.shutdown)
    rospy.spin()
