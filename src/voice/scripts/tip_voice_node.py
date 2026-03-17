#!/usr/bin/env python3
"""
tip_voice_node.py
=================122
PTT（Push-to-Talk）語音辨識 ROS 節點。

操作方式：
    - 按住 空白鍵 → 開始錄音
    - 放開 空白鍵 → 停止錄音，送 Whisper API 轉文字
    - 按 Esc / Ctrl-C → 退出節點

重用模組（來自 src/）：
    - ptt_recorder.py        : PTT 錄音（按/放控制開始結束）
    - whisper_transcriber.py : Whisper API 語音轉文字

發布 topic（與 voice_node.py 相同，方便切換）：
    /voice/transcript  (std_msgs/String)  — 轉錄文字
    /voice/status      (std_msgs/String)  — 目前狀態
"""
import os
import sys
import threading

import rospy
from std_msgs.msg import String
from pynput import keyboard

# ── src/ 模組路徑 ──
_PKG_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SRC_DIR  = os.path.join(_PKG_DIR, "src")
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)

from ptt_recorder        import PTTRecorder
from whisper_transcriber import WhisperTranscriber   # 重用現有模組


# ──────────────────────────── ROS 節點 ────────────────────────────────────
class TipVoiceNode:
    """PTT 語音辨識 ROS 節點（按住空白鍵錄音）。"""

    def __init__(self):
        rospy.init_node("tip_voice_node", anonymous=False)

        # ── Publishers（與 voice_node 同 topic，可互換使用）──
        self._pub_transcript = rospy.Publisher(
            "/voice/transcript", String, queue_size=5)
        self._pub_status = rospy.Publisher(
            "/voice/status", String, queue_size=5)

        # ── 初始化模組（重用 src/）──
        rospy.loginfo("[tip_voice] 初始化 PTT 錄音器...")
        self._recorder = PTTRecorder(sample_rate=16000)

        rospy.loginfo("[tip_voice] 初始化 Whisper 轉錄器（從 .env 讀取 API Key）...")
        self._transcriber = WhisperTranscriber(
            model    = "whisper-1",
            language = "zh",
        )  # api_key 自動從 src/.env 讀取

        # 防止重複觸發（空白鍵 on_press 可能連續觸發）
        self._is_recording = False
        self._lock         = threading.Lock()

        # ── 啟動鍵盤監聽 ──
        self._kb_listener = keyboard.Listener(
            on_press   = self._on_key_press,
            on_release = self._on_key_release,
        )
        self._kb_listener.start()

        self._publish_status("idle")
        rospy.loginfo("[tip_voice] 節點就緒。")
        rospy.loginfo("[tip_voice] ▶  按住 空白鍵 開始錄音，放開結束並送出辨識。")
        rospy.loginfo("[tip_voice]    按 Esc 退出節點。")

    # ── 鍵盤事件 ─────────────────────────────────────────────────────────

    def _on_key_press(self, key) -> None:
        """按下空白鍵 → 開始錄音（避免 key repeat 重複觸發）。"""
        if key != keyboard.Key.space:
            return
        with self._lock:
            if self._is_recording:
                return          # 已在錄音，忽略 key repeat
            self._is_recording = True

        rospy.loginfo("[tip_voice] 🎙️  錄音中...")
        self._publish_status("recording")
        self._recorder.start_recording()

    def _on_key_release(self, key) -> None:
        """放開空白鍵 → 停止錄音並送出辨識；Esc → 退出。"""
        if key == keyboard.Key.esc:
            rospy.loginfo("[tip_voice] 使用者按下 Esc，關閉節點。")
            rospy.signal_shutdown("user pressed Esc")
            return False          # 停止 pynput listener

        if key != keyboard.Key.space:
            return

        with self._lock:
            if not self._is_recording:
                return
            self._is_recording = False

        # 在新執行緒中處理，避免阻塞鍵盤監聽
        threading.Thread(target=self._process_recording, daemon=True).start()

    # ── 錄音 + 辨識流程 ──────────────────────────────────────────────────

    def _process_recording(self) -> None:
        """停止錄音 → 存音檔 → 送 Whisper API → 發布結果。"""
        try:
            rospy.loginfo("[tip_voice] 🔄  處理錄音...")
            self._publish_status("processing")

            wav_bytes = self._recorder.stop_recording()

            if wav_bytes is None:
                rospy.logwarn("[tip_voice] 錄音過短，忽略。")
                self._publish_status("idle")
                return

            # ── 儲存音檔供除錯確認 ──
            import datetime
            debug_dir = "/tmp/voice_debug"
            os.makedirs(debug_dir, exist_ok=True)
            ts       = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            wav_path = os.path.join(debug_dir, f"recording_{ts}.wav")
            with open(wav_path, "wb") as f:
                f.write(wav_bytes)
            rospy.loginfo(f"[tip_voice] 💾  音檔已儲存：{wav_path}")

            text = self._transcriber.transcribe(wav_bytes)

            if text:
                rospy.loginfo(f"[tip_voice] 📝  轉錄結果：「{text}」")
                self._publish_transcript(text)
            else:
                rospy.logwarn("[tip_voice] Whisper 回傳空字串。")

            self._publish_status("idle")
            rospy.loginfo("[tip_voice] ▶  按住 空白鍵 繼續錄音。")

        except Exception as e:
            rospy.logerr(f"[tip_voice] 錯誤：{e}")
            self._publish_status(f"error: {e}")

    # ── 發布輔助方法 ──────────────────────────────────────────────────────

    def _publish_transcript(self, text: str) -> None:
        msg = String()
        msg.data = text
        self._pub_transcript.publish(msg)

    def _publish_status(self, status: str) -> None:
        msg = String()
        msg.data = status
        self._pub_status.publish(msg)

    # ── 清理 ──────────────────────────────────────────────────────────────

    def shutdown(self) -> None:
        rospy.loginfo("[tip_voice] 節點關閉。")
        self._kb_listener.stop()
        self._recorder.close()


# ──────────────────────────── 程式入口 ────────────────────────────────────
if __name__ == "__main__":
    node = TipVoiceNode()
    rospy.on_shutdown(node.shutdown)
    rospy.spin()
