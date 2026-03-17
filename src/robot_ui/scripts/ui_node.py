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

        self.width = 1000
        self.height = 700
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
        self.btn_reschedule_rect = (650, 600, 970, 645)  # (x1, y1, x2, y2)
        self.btn_feedback_msg   = ""   # 按下後顯示的回饋文字
        self.btn_feedback_timer = 0    # 倒數顯示幾幀

        # Subscribers
        rospy.Subscriber("/high_level_stream", String, self.high_level_cb)
        rospy.Subscriber("/optimized_schedule", String, self.schedule_cb)
        rospy.Subscriber("/current_task", String, self.current_task_cb)
        rospy.Subscriber("/robot_status", Int32, self.status_cb)

        rospy.loginfo("[UI Node] Ready. Showing OpenCV Window.")

        # 設定滑鼠回呼
        cv2.namedWindow("Robot UI Dashboard")
        cv2.setMouseCallback("Robot UI Dashboard", self._mouse_callback)

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
        # Create dark background
        img_np = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        img_np[:] = (30, 30, 30) # Dark gray

        # Convert to PIL for text drawing
        img_pil = Image.fromarray(img_np)
        draw = ImageDraw.Draw(img_pil)

        # Header
        status_text = "狀態: 閒置 (Idle)" if self.robot_status == 0 else "狀態: 執行中 (Busy)"
        status_color = (100, 255, 100) if self.robot_status == 0 else (255, 100, 100)
        self.draw_text(draw, "機器人任務看板 (Robot UI)", (20, 20), self.font_title, (200, 200, 255))
        self.draw_text(draw, status_text, (650, 25), self.font_text, status_color)
        
        draw.line([(20, 70), (self.width-20, 70)], fill=(100, 100, 100), width=2)

        # High Level Task
        self.draw_text(draw, "當前語音大任務:", (20, 90), self.font_text, (255, 255, 100))
        self.draw_text(draw, f"   {self.high_level_task_name}", (20, 130), self.font_title, (255, 255, 255))

        draw.line([(20, 185), (self.width-20, 185)], fill=(100, 100, 100), width=2)

        # Current Task
        self.draw_text(draw, "正在執行 (Current Action):", (20, 205), self.font_text, (100, 255, 255))
        if self.current_task and self.robot_status == 1:
            tid = self.current_task.get("global_id", "?")
            act = self.current_task.get("action_type", "?")
            loc = self.current_task.get("location_id", "?")
            self.draw_text(draw, f"   ▶ [{tid}] {act} - 地點 ID: {loc}", (20, 245), self.font_title, (100, 255, 100))
        else:
            self.draw_text(draw, "   (無)", (20, 245), self.font_text, (150, 150, 150))

        draw.line([(20, 305), (self.width-20, 305)], fill=(100, 100, 100), width=2)

        # Queue
        self.draw_text(draw, f"待辦排程 Queue ({len(self.task_queue)} tasks):", (20, 325), self.font_text, (255, 150, 100))
        y_offset = 365
        for i, task in enumerate(self.task_queue[:8]): # Display up to 8 tasks
            tid = task.get("global_id", "?")
            act = task.get("action_type", "?")
            loc = task.get("location_id", "?")
            self.draw_text(draw, f"   {i+1}. [{tid}] {act} - 地點 ID: {loc}", (20, y_offset), self.font_text, (200, 200, 200))
            y_offset += 35
            
        if len(self.task_queue) > 8:
            self.draw_text(draw, f"   ... 還有 {len(self.task_queue)-8} 個任務", (20, y_offset), self.font_small, (150, 150, 150))

        # ── 重新排程按鈕 ──────────────────────────────────────────────────
        x1, y1, x2, y2 = self.btn_reschedule_rect
        btn_color = (60, 60, 180)   # 深藍色
        draw.rectangle([x1, y1, x2, y2], fill=btn_color, outline=(150, 150, 255), width=2)
        self.draw_text(draw, "重新排程 (Reschedule)", (x1 + 18, y1 + 10), self.font_text, (255, 255, 255))

        # 按鈕回饋訊息（顯示一段時間後消失）
        if self.btn_feedback_timer > 0:
            self.draw_text(draw, self.btn_feedback_msg, (x1, y2 + 8), self.font_small, (180, 255, 180))
            self.btn_feedback_timer -= 1

        # Convert back to OpenCV
        final_img = np.array(img_pil)
        
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
