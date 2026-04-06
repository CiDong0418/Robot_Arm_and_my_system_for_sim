#!/usr/bin/env python3
"""
assistant_reply_tts_node_host.py
================================
主機版 TTS 節點：訂閱 /assistant_reply，使用 Edge TTS 播放到主機預設音訊輸出
（通常就是已連線的藍牙喇叭）。

需求:
- Python 套件: edge-tts
- 播放工具: mpg123, paplay (推薦), aplay (fallback)

用途:
- 讓容器內的 voice_node 只負責辨識與發布 /assistant_reply
- 主機端此節點負責真正音訊輸出（藍牙）
"""

import os
import subprocess
import tempfile

import edge_tts
import rospy
from std_msgs.msg import String


class AssistantReplyTTSHostNode:
    def __init__(self):
        rospy.init_node("assistant_reply_tts_node_host", anonymous=False)

        self._voice = rospy.get_param("~voice", "zh-TW-HsiaoChenNeural")
        self._rate = rospy.get_param("~rate", "+0%")
        self._volume = rospy.get_param("~volume", "+0%")
        self._pitch = rospy.get_param("~pitch", "+0Hz")
        self._max_chars = int(rospy.get_param("~max_chars", 240))

        self._prefer_pulse = bool(rospy.get_param("~prefer_pulse", True))
        self._alsa_device = rospy.get_param("~alsa_device", "default")

        self._sub = rospy.Subscriber("/assistant_reply", String, self._on_reply, queue_size=20)
        rospy.loginfo("[assistant_tts_host] Ready. Subscribing /assistant_reply")
        rospy.loginfo(
            f"[assistant_tts_host] voice={self._voice}, prefer_pulse={self._prefer_pulse}, "
            f"alsa_device={self._alsa_device}"
        )

    def _on_reply(self, msg: String) -> None:
        text = (msg.data or "").strip()
        if not text:
            return

        if len(text) > self._max_chars:
            text = text[: self._max_chars]

        rospy.loginfo(f"[assistant_tts_host] 🔊 {text}")

        mp3_path = None
        wav_path = None
        try:
            mp3_path = self._synthesize_mp3(text)
            wav_path = self._decode_to_wav(mp3_path)
            self._play_wav(wav_path)
        except Exception as exc:
            rospy.logerr(f"[assistant_tts_host] 播放失敗: {exc}")
        finally:
            for path in (mp3_path, wav_path):
                if path and os.path.isfile(path):
                    try:
                        os.remove(path)
                    except OSError:
                        pass

    def _synthesize_mp3(self, text: str) -> str:
        temp_mp3 = tempfile.NamedTemporaryFile(prefix="assistant_reply_", suffix=".mp3", delete=False)
        temp_mp3.close()

        communicator = edge_tts.Communicate(
            text=text,
            voice=self._voice,
            rate=self._rate,
            volume=self._volume,
            pitch=self._pitch,
        )
        communicator.save_sync(temp_mp3.name)
        return temp_mp3.name

    def _decode_to_wav(self, mp3_path: str) -> str:
        temp_wav = tempfile.NamedTemporaryFile(prefix="assistant_reply_", suffix=".wav", delete=False)
        temp_wav.close()

        decode = subprocess.run(
            ["mpg123", "-q", "-w", temp_wav.name, mp3_path],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
        )
        if decode.returncode != 0:
            raise RuntimeError(decode.stderr.strip() or "mpg123 解碼失敗")

        return temp_wav.name

    def _play_wav(self, wav_path: str) -> None:
        errors = []

        if self._prefer_pulse:
            pulse_play = subprocess.run(
                ["paplay", wav_path],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
            )
            if pulse_play.returncode == 0:
                return
            errors.append(f"paplay: {(pulse_play.stderr or '').strip()}")

        alsa_candidates = [self._alsa_device, "default", "sysdefault", "plughw:CARD=PCH,DEV=0", "hw:CARD=PCH,DEV=0"]
        tried = set()
        for dev in alsa_candidates:
            if not dev or dev in tried:
                continue
            tried.add(dev)

            play = subprocess.run(
                ["aplay", "-D", dev, wav_path],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
            )
            if play.returncode == 0:
                return
            errors.append(f"aplay -D {dev}: {(play.stderr or '').strip()}")

        fallback = subprocess.run(
            ["aplay", wav_path],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
        )
        if fallback.returncode == 0:
            return

        errors.append(f"aplay(no -D): {(fallback.stderr or '').strip()}")
        raise RuntimeError(" ; ".join(errors))


if __name__ == "__main__":
    try:
        AssistantReplyTTSHostNode()
        rospy.spin()
    except rospy.ROSInterruptException:
        pass
