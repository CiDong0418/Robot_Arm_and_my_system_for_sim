#!/usr/bin/env python3
import rospy
import cv2
import numpy as np
import threading
from PIL import Image, ImageDraw, ImageFont
import json
import os
import urllib.request

# Suppress annoying Qt font warning from OpenCV 4.x on headless/Docker systems
os.environ["QT_LOGGING_RULES"] = "qt.qpa.fonts=false"

from std_msgs.msg import String, Int32
from std_srvs.srv import Trigger

class RobotUI:
    def __init__(self):
        rospy.init_node('robot_ui_node', anonymous=True)

        self.width = 700
        self.height = 1800
        self.rotate_portrait = rospy.get_param('~rotate_portrait', True)
        self.rotate_direction = rospy.get_param('~rotate_direction', 'counterclockwise')
        self.font_path = os.path.join(os.path.dirname(__file__), "NotoSansTC-Regular.ttf")
        self._download_font_if_needed()
        
        try:
            self.font_title = ImageFont.truetype(self.font_path, 32)
            self.font_text = ImageFont.truetype(self.font_path, 24)
            self.font_small = ImageFont.truetype(self.font_path, 20)
        except Exception as e:
            rospy.logerr(f"無法載入字型: {e}")
            self.font_title = ImageFont.load_default()
            self.font_text = ImageFont.load_default()
            self.font_small = ImageFont.load_default()

        # State Variables
        self.robot_status = 0 # 0: Idle, 1: Busy
        self.high_level_task_name = "等待語音指令..."
        self.current_task = None
        self.task_queue = []

        # 重新排程按鈕狀態
        self.margin = 24
        self.btn_height = 72
        self.btn_reschedule_rect = (
            self.margin,
            self.height - self.margin - self.btn_height,
            self.width - self.margin,
            self.height - self.margin
        )  # (x1, y1, x2, y2)
        self.btn_feedback_msg   = ""   # 按下後顯示的回饋文字
        self.btn_feedback_timer = 0    # 倒數顯示幾幀

        # 影片循環播放設定（可選）
        self.video_path = rospy.get_param('~video_path', '')
        self.video_loop_start_sec = float(rospy.get_param('~video_loop_start_sec', 14.5))
        self.video_loop_end_sec = float(rospy.get_param('~video_loop_end_sec', 17.5))
        self.video_cap = None
        self.video_enabled = False
        self.video_duration_sec = 0.0

        # Subscribers
        rospy.Subscriber("/high_level_stream", String, self.high_level_cb)
        rospy.Subscriber("/optimized_schedule", String, self.schedule_cb)
        rospy.Subscriber("/current_task", String, self.current_task_cb)
        rospy.Subscriber("/robot_status", Int32, self.status_cb)

        rospy.loginfo("[UI Node] Ready. Showing OpenCV Window.")

        # 設定滑鼠回呼
        cv2.namedWindow("Robot UI Dashboard")
        cv2.setMouseCallback("Robot UI Dashboard", self._mouse_callback)
        rospy.on_shutdown(self._cleanup)

        self._init_video_player()

    def _init_video_player(self):
        if not self.video_path:
            return

        if not os.path.exists(self.video_path):
            rospy.logwarn(f"[UI] 找不到影片: {self.video_path}")
            return

        cap = cv2.VideoCapture(self.video_path)
        if not cap.isOpened():
            rospy.logwarn(f"[UI] 無法開啟影片: {self.video_path}")
            return

        fps = cap.get(cv2.CAP_PROP_FPS)
        if fps is None or fps <= 0:
            fps = 30.0

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if total_frames > 0:
            self.video_duration_sec = total_frames / fps

        self.video_loop_start_sec = max(0.0, self.video_loop_start_sec)

        if self.video_duration_sec > 0:
            self.video_loop_start_sec = min(self.video_loop_start_sec, self.video_duration_sec)

        if self.video_loop_end_sec <= self.video_loop_start_sec:
            self.video_loop_end_sec = self.video_duration_sec if self.video_duration_sec > 0 else (self.video_loop_start_sec + 5.0)

        if self.video_duration_sec > 0:
            self.video_loop_end_sec = min(self.video_loop_end_sec, self.video_duration_sec)

        if self.video_loop_end_sec <= self.video_loop_start_sec:
            self.video_loop_end_sec = self.video_loop_start_sec + 0.1

        self.video_cap = cap
        self.video_enabled = True
        self._seek_video_to_loop_start()
        rospy.loginfo(
            f"[UI] 影片循環啟用: {self.video_path} | "
            f"{self.video_loop_start_sec:.2f}s -> {self.video_loop_end_sec:.2f}s"
        )

    def _seek_video_to_loop_start(self):
        if self.video_cap is None:
            return
        self.video_cap.set(cv2.CAP_PROP_POS_MSEC, self.video_loop_start_sec * 1000.0)

    def _get_video_loop_frame(self):
        if not self.video_enabled or self.video_cap is None:
            return None

        pos_sec = self.video_cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0
        if pos_sec >= self.video_loop_end_sec:
            self._seek_video_to_loop_start()

        ret, frame = self.video_cap.read()
        if not ret:
            self._seek_video_to_loop_start()
            ret, frame = self.video_cap.read()
            if not ret:
                return None

        pos_after = self.video_cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0
        if pos_after > self.video_loop_end_sec:
            self._seek_video_to_loop_start()
            ret, frame = self.video_cap.read()
            if not ret:
                return None

        return frame

    def _cleanup(self):
        if self.video_cap is not None:
            self.video_cap.release()
        cv2.destroyAllWindows()

    def _download_font_if_needed(self):
        if not os.path.exists(self.font_path):
            rospy.loginfo("Downloading NotoSansTC Font for UI rendering...")
            url = "https://github.com/notofonts/noto-cjk/raw/main/Sans/OTF/TraditionalChinese/NotoSansCJKtc-Regular.otf"
            try:
                urllib.request.urlretrieve(url, self.font_path)
                rospy.loginfo("Font downloaded successfully.")
            except Exception as e:
                rospy.logwarn(f"Failed to download font: {e}, will use fallback.")

    def high_level_cb(self, msg):
        try:
            data = json.loads(msg.data)
            self.high_level_task_name = data.get("name", "Unknown Task")
        except:
            pass

    def schedule_cb(self, msg):
        try:
            self.task_queue = json.loads(msg.data)
        except:
            pass

    def current_task_cb(self, msg):
        try:
            self.current_task = json.loads(msg.data)
            # Remove from queue if exists to keep them in sync
            curr_id = self.current_task.get("global_id")
            self.task_queue = [t for t in self.task_queue if t.get("global_id") != curr_id]
        except:
            pass

    def status_cb(self, msg):
        self.robot_status = msg.data
        if self.robot_status == 0:
            # If idle, clear the current task execution display
            self.current_task = None

    def _mouse_callback(self, event, x, y, flags, param):
        """偵測滑鼠左鍵點擊，判斷是否點到「重新排程」按鈕。"""
        if event != cv2.EVENT_LBUTTONDOWN:
            return

        if self.rotate_portrait:
            if self.rotate_direction == 'counterclockwise':
                x, y = self.width - 1 - y, x
            else:
                x, y = y, self.height - 1 - x

        x1, y1, x2, y2 = self.btn_reschedule_rect
        if x1 <= x <= x2 and y1 <= y <= y2:
            # 在獨立執行緒呼叫，避免阻塞 UI 主迴圈
            threading.Thread(target=self._call_start_scheduling, daemon=True).start()

    def _call_start_scheduling(self):
        """呼叫 /start_scheduling service 觸發重新排程。"""
        try:
            rospy.wait_for_service('/start_scheduling', timeout=2.0)
            call = rospy.ServiceProxy('/start_scheduling', Trigger)
            resp = call()
            if resp.success:
                self.btn_feedback_msg   = "排程已觸發！"
                self.btn_feedback_timer = 30   # 顯示 30 幀（約 3 秒）
                rospy.loginfo("[UI] 重新排程觸發成功")
            else:
                self.btn_feedback_msg   = f"警告: {resp.message}"
                self.btn_feedback_timer = 30
                rospy.logwarn(f"[UI] 排程回傳失敗: {resp.message}")
        except Exception as e:
            self.btn_feedback_msg   = "錯誤: 服務未啟動"
            self.btn_feedback_timer = 30
            rospy.logerr(f"[UI] 無法呼叫 /start_scheduling: {e}")

    def draw_text(self, draw, text, position, font, color=(255, 255, 255)):
        draw.text(position, text, font=font, fill=color)

    def update_display(self):
        if self.video_enabled:
            frame = self._get_video_loop_frame()
            if frame is not None:
                final_img = cv2.resize(frame, (self.width, self.height), interpolation=cv2.INTER_AREA)

                if self.rotate_portrait:
                    if self.rotate_direction == 'counterclockwise':
                        final_img = cv2.rotate(final_img, cv2.ROTATE_90_COUNTERCLOCKWISE)
                    else:
                        final_img = cv2.rotate(final_img, cv2.ROTATE_90_CLOCKWISE)

                cv2.imshow("Robot UI Dashboard", final_img)
                cv2.waitKey(1)
                return

        # Create dark background
        img_np = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        img_np[:] = (30, 30, 30) # Dark gray

        # Convert to PIL for text drawing
        img_pil = Image.fromarray(img_np)
        draw = ImageDraw.Draw(img_pil)

        # Header
        left = self.margin
        right = self.width - self.margin
        status_text = "狀態: 閒置 (Idle)" if self.robot_status == 0 else "狀態: 執行中 (Busy)"
        status_color = (100, 255, 100) if self.robot_status == 0 else (255, 100, 100)
        self.draw_text(draw, "機器人任務看板", (left, 18), self.font_title, (200, 200, 255))
        self.draw_text(draw, status_text, (left, 64), self.font_text, status_color)
        
        draw.line([(left, 106), (right, 106)], fill=(100, 100, 100), width=2)

        # High Level Task
        self.draw_text(draw, "當前語音大任務:", (left, 124), self.font_text, (255, 255, 100))
        self.draw_text(draw, f"{self.high_level_task_name}", (left, 162), self.font_title, (255, 255, 255))

        draw.line([(left, 218), (right, 218)], fill=(100, 100, 100), width=2)

        # Current Task
        self.draw_text(draw, "正在執行 (Current Action):", (left, 238), self.font_text, (100, 255, 255))
        if self.current_task and self.robot_status == 1:
            tid = self.current_task.get("global_id", "?")
            act = self.current_task.get("action_type", "?")
            loc = self.current_task.get("location_id", "?")
            self.draw_text(draw, f"▶ [{tid}] {act}", (left, 278), self.font_title, (100, 255, 100))
            self.draw_text(draw, f"地點 ID: {loc}", (left, 320), self.font_text, (170, 255, 170))
        else:
            self.draw_text(draw, "(無)", (left, 278), self.font_text, (150, 150, 150))

        draw.line([(left, 370), (right, 370)], fill=(100, 100, 100), width=2)

        # Queue
        self.draw_text(draw, f"待辦排程 Queue ({len(self.task_queue)} tasks):", (left, 392), self.font_text, (255, 150, 100))
        y_offset = 432

        x1, y1, x2, y2 = self.btn_reschedule_rect
        queue_bottom = y1 - 56
        line_height = 42
        max_queue_rows = max(1, (queue_bottom - y_offset) // line_height)

        for i, task in enumerate(self.task_queue[:max_queue_rows]):
            tid = task.get("global_id", "?")
            act = task.get("action_type", "?")
            loc = task.get("location_id", "?")
            self.draw_text(draw, f"{i+1}. [{tid}] {act}", (left, y_offset), self.font_text, (200, 200, 200))
            self.draw_text(draw, f"   地點 ID: {loc}", (left, y_offset + 24), self.font_small, (170, 170, 170))
            y_offset += line_height
            
        if len(self.task_queue) > max_queue_rows:
            self.draw_text(draw, f"... 還有 {len(self.task_queue)-max_queue_rows} 個任務", (left, min(y_offset + 8, queue_bottom)), self.font_small, (150, 150, 150))

        # ── 重新排程按鈕 ──────────────────────────────────────────────────
        btn_color = (60, 60, 180)   # 深藍色
        draw.rectangle([x1, y1, x2, y2], fill=btn_color, outline=(150, 150, 255), width=2)
        self.draw_text(draw, "重新排程 (Reschedule)", (x1 + 24, y1 + 20), self.font_text, (255, 255, 255))

        # 按鈕回饋訊息（顯示一段時間後消失）
        if self.btn_feedback_timer > 0:
            self.draw_text(draw, self.btn_feedback_msg, (x1, y1 - 34), self.font_small, (180, 255, 180))
            self.btn_feedback_timer -= 1

        # Convert back to OpenCV
        final_img = np.array(img_pil)

        if self.rotate_portrait:
            if self.rotate_direction == 'counterclockwise':
                final_img = cv2.rotate(final_img, cv2.ROTATE_90_COUNTERCLOCKWISE)
            else:
                final_img = cv2.rotate(final_img, cv2.ROTATE_90_CLOCKWISE)
        
        # Display CV2 window
        cv2.imshow("Robot UI Dashboard", final_img)
        cv2.waitKey(1)

if __name__ == '__main__':
    try:
        ui = RobotUI()
        
        # Main GUI Loop (runs in main thread)
        rate = rospy.Rate(10) # 10 Hz
        while not rospy.is_shutdown():
            ui.update_display()
            rate.sleep()
            
    except rospy.ROSInterruptException:
        pass
