#!/usr/bin/env python3
"""
assistant_reply_tts_node.py
==========================
訂閱 /assistant_reply，將文字轉語音並播放。

流程：
1) 訂閱 /assistant_reply (std_msgs/String)
2) 呼叫 Microsoft Edge TTS 產生 mp3
3) 使用 mpg123 播放
"""

import os
import subprocess
import tempfile

import rospy
import edge_tts
from std_msgs.msg import String


class AssistantReplyTTSNode:
    def __init__(self):
        rospy.init_node("assistant_reply_tts_node", anonymous=False)

        self._voice = rospy.get_param("~voice", "zh-TW-HsiaoChenNeural")
        self._rate = rospy.get_param("~rate", "+0%")
        self._volume = rospy.get_param("~volume", "+0%")
        self._pitch = rospy.get_param("~pitch", "+0Hz")
        self._playback_device = rospy.get_param(
            "~playback_device",
            os.environ.get("VOICE_PLAYBACK_DEVICE", "default:CARD=PCH"),
        )
        self._max_chars = int(rospy.get_param("~max_chars", 240))
        self._prefer_pulse = bool(rospy.get_param("~prefer_pulse", True))

        self._sub = rospy.Subscriber("/assistant_reply", String, self._on_reply, queue_size=10)
        rospy.loginfo("[assistant_tts] Ready. Subscribing /assistant_reply")
        rospy.loginfo(
            f"[assistant_tts] backend=edge-tts, voice={self._voice}, "
            f"playback_device={self._playback_device or 'default'}"
        )

    def _on_reply(self, msg: String) -> None:
        text = (msg.data or "").strip()
        if not text:
            return

        if len(text) > self._max_chars:
            text = text[: self._max_chars]

        rospy.loginfo(f"[assistant_tts] 🔊 {text}")

        try:
            mp3_path = self._synthesize_mp3(text)
            self._play_mp3(mp3_path)
        except Exception as exc:
            rospy.logerr(f"[assistant_tts] 播放失敗: {exc}")

    def _synthesize_mp3(self, text: str) -> str:
        tmp = tempfile.NamedTemporaryFile(prefix="assistant_reply_", suffix=".mp3", delete=False)
        tmp.close()

        communicate = edge_tts.Communicate(
            text=text,
            voice=self._voice,
            rate=self._rate,
            volume=self._volume,
            pitch=self._pitch,
        )
        communicate.save_sync(tmp.name)
        return tmp.name

    def _play_mp3(self, mp3_path: str) -> None:
        wav_path = tempfile.mktemp(prefix="assistant_reply_", suffix=".wav")
        try:
            decode = subprocess.run(
                ["mpg123", "-q", "-w", wav_path, mp3_path],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
            )
            if decode.returncode != 0:
                raise RuntimeError(decode.stderr.strip() or "mpg123 解碼失敗")

            # 若有主機 PulseAudio/PipeWire 映射，優先用 paplay（可直接走藍牙預設輸出）
            if self._prefer_pulse and os.environ.get("PULSE_SERVER"):
                pulse_play = subprocess.run(
                    ["paplay", wav_path],
                    check=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                if pulse_play.returncode == 0:
                    return

            play_errors = []
            device_candidates = []
            if self._playback_device:
                device_candidates.append(self._playback_device)
            device_candidates.extend([
                "default:CARD=PCH",
                "sysdefault:CARD=PCH",
                "plughw:CARD=PCH,DEV=0",
                "hw:CARD=PCH,DEV=0",
            ])

            tried = set()
            for device in device_candidates:
                if device in tried:
                    continue
                tried.add(device)

                play = subprocess.run(
                    ["aplay", "-D", device, wav_path],
                    check=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                if play.returncode == 0:
                    return

                err = (play.stderr or "").strip()
                play_errors.append(f"{device}: {err}")

            # 最後嘗試系統預設（不指定 -D）
            fallback = subprocess.run(
                ["aplay", wav_path],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
            )
            if fallback.returncode == 0:
                return

            err = (fallback.stderr or "").strip()
            play_errors.append(f"(no -D): {err}")
            raise RuntimeError(" ; ".join(play_errors))
        finally:
            try:
                os.remove(mp3_path)
            except OSError:
                pass
            try:
                if os.path.isfile(wav_path):
                    os.remove(wav_path)
            except OSError:
                pass


if __name__ == "__main__":
    try:
        AssistantReplyTTSNode()
        rospy.spin()
    except rospy.ROSInterruptException:
        pass
