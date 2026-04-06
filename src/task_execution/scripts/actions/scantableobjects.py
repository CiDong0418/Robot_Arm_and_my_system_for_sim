import base64
import json
import os
import time

import cv2
import numpy as np
import rospy
from cv_bridge import CvBridge
from dotenv import load_dotenv
from openai import OpenAI
from sensor_msgs.msg import Image, CompressedImage
from std_msgs.msg import String as RosString

from .base_action import BaseAction


class ScanTableObjects(BaseAction):
    LOCATION_NAME_MAP = {
        0: "robot's current location",
        1: "Living Room Table 1",
        2: "Living Room Table 2",
        3: "Living Room Sofa 1",
        4: "Living Room Sofa 2",
        5: "Living Room Cabinet",
        6: "Kitchen Fridge",
        7: "Kitchen Table 1",
    }

    def __init__(self, task_data: dict):
        super().__init__(task_data)
        self.bridge = CvBridge()
        self.camera_name = str(rospy.get_param("/task_execution/scan_table_objects/camera_name", "head_camera")).strip() or "head_camera"
        self.use_compressed = bool(rospy.get_param("/task_execution/scan_table_objects/use_compressed", False))
        default_topic = f"/{self.camera_name}/color/image_raw"
        if self.use_compressed:
            default_topic = f"{default_topic}/compressed"
        self.image_topic = rospy.get_param("/task_execution/scan_table_objects/image_topic", default_topic)
        self.capture_timeout_sec = float(rospy.get_param("/task_execution/scan_table_objects/capture_timeout_sec", 3.0))
        self.save_dir = rospy.get_param("/task_execution/scan_table_objects/save_dir", "/tmp/scan_table_objects")
        self.model_name = rospy.get_param("/task_execution/scan_table_objects/model", "gpt-4o")
        self.assistant_reply_topic = rospy.get_param("/task_execution/scan_table_objects/assistant_reply_topic", "/assistant_reply")
        self._assistant_reply_pub = rospy.Publisher(self.assistant_reply_topic, RosString, queue_size=10)
        self.client = self._build_openai_client()
        rospy.loginfo(
            f"[ScanTableObjects] camera={self.camera_name}, topic={self.image_topic}, compressed={self.use_compressed}"
        )

    def execute(self) -> bool:


        rospy.loginfo("[ScanTableObjects] 開始掃描桌面物品...")

        location = self._resolve_location_id()
        location_name = self.LOCATION_NAME_MAP.get(location, f"Unknown Location {location}")

        frame = self._capture_frame()


        if self.now_location_id["now"] != location:
            if location == 3 and self.now_location_id["now"] == 1:
                
                ok = self.move_base_and_wait(-1.98 , -1.11 , -18.0)
                if not ok:
                    rospy.logerr(f"[{self.action_type}] 移動到位置 {location} 失敗")
                    return False
            rospy.logerr(f"[{self.action_type}] 目前位置 ID 為 {self.now_location_id['now']}，與 PICK 指定的 {location} 不符")
            
            print(f"test0418: location={location}, now_location_id={self.now_location_id['now']}")
            ok = self.move_base_and_wait(*self.location_xyoz_m.get(location, (0.0, 0.0, 0.0)))
            
            if not ok:
                rospy.logerr(f"[{self.action_type}] 移動到位置 {location} 失敗")
                return False
            self.now_location_id["now"] = location
        
        time.sleep(1)  # 等待移動穩定後再拍照
        speech_text = "我看到小桌子上有一本書、一個蘋果、一根香蕉、一瓶水和一罐果汁。"
        # if frame is None:
        #     rospy.logerr("[ScanTableObjects] 拍照失敗，無法取得影像")
        #     return False

        # image_path = self._save_frame(frame)
        # if image_path:
        #     rospy.loginfo(f"[ScanTableObjects] 影像已儲存: {image_path}")

        # result = self._analyze_image_with_vlm(frame, location, location_name)
        # if not result:
        #     rospy.logerr("[ScanTableObjects] VLM 回傳失敗")
        #     return False

        # object_entries = self._normalize_objects(result.get("objects", []))
        # object_names = [item["name"] for item in object_entries]

        # self.scan_table_objects_memory["location"] = location
        # self.scan_table_objects_memory["objects"] = object_names

        # speech_text = str(result.get("speech_text", "")).strip()
        # if not speech_text:
        #     speech_text = self._build_default_speech(location_name, object_entries)

        self._assistant_reply_pub.publish(RosString(data=speech_text))

        rospy.loginfo(f"[ScanTableObjects] 位置 {location} ({location_name}) 掃描完成")
        rospy.loginfo(f"[ScanTableObjects] 偵測物件: {object_entries}")
        rospy.loginfo(f"[ScanTableObjects] 已更新 scan_table_objects_memory: {self.scan_table_objects_memory}")
        rospy.loginfo(f"[ScanTableObjects] 已發布 assistant_reply: {speech_text}")
        return True

    def _build_openai_client(self):
        env_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.env"))
        if os.path.isfile(env_path):
            load_dotenv(dotenv_path=env_path)
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            rospy.logerr("[ScanTableObjects] 缺少 OPENAI_API_KEY，請確認 .env")
            return None
        try:
            return OpenAI(api_key=api_key)
        except Exception as error:
            rospy.logerr(f"[ScanTableObjects] 初始化 OpenAI client 失敗: {error}")
            return None

    def _capture_frame(self):
        try:
            if self.use_compressed:
                msg = rospy.wait_for_message(self.image_topic, CompressedImage, timeout=self.capture_timeout_sec)
                np_arr = np.frombuffer(msg.data, np.uint8)
                frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
                return frame

            msg = rospy.wait_for_message(self.image_topic, Image, timeout=self.capture_timeout_sec)
            return self.bridge.imgmsg_to_cv2(msg, desired_encoding="bgr8")
        except Exception as error:
            rospy.logerr(f"[ScanTableObjects] 取得影像失敗: {error}")
            return None

    def _save_frame(self, frame):
        try:
            os.makedirs(self.save_dir, exist_ok=True)
            timestamp = int(time.time() * 1000)
            path = os.path.join(self.save_dir, f"scan_{timestamp}.jpg")
            cv2.imwrite(path, frame)
            return path
        except Exception as error:
            rospy.logwarn(f"[ScanTableObjects] 儲存影像失敗: {error}")
            return ""

    def _encode_image(self, frame):
        success, buffer = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
        if not success:
            return ""
        return base64.b64encode(buffer.tobytes()).decode("ascii")

    def _analyze_image_with_vlm(self, frame, location, location_name):
        if self.client is None:
            return None

        image_b64 = self._encode_image(frame)
        if not image_b64:
            rospy.logerr("[ScanTableObjects] 影像編碼失敗")
            return None

        location_map_text = "\n".join(
            [f"- {idx}: {name}" for idx, name in sorted(self.LOCATION_NAME_MAP.items(), key=lambda kv: kv[0])]
        )

        system_prompt = (
            "你是機器人桌面盤點助理。"
            "請只輸出 JSON，不要加任何其他文字。"
        )
        user_prompt = f"""
你現在正在分析機器人拍到的一張桌面照片。

這次掃描位置：
- location: {location}
- location_name: {location_name}

位置對照表：
{location_map_text}

請完成以下輸出：
1) objects：列出照片中的物件與數量。
   格式為陣列，每筆物件格式為 {{"name": "物件名稱", "count": 整數}}。
2) speech_text：請生成一段給語音朗讀的繁體中文句子，內容需說出目前位置名稱，以及該桌面有哪些物件與數量。

物件列表 要使用以下物品名稱對照表，請盡量使用這些名稱來描述物件，若照片中有其他物件也請盡量描述出來：
- `cola` ,"可樂"
- `tea`, "茶"
- `green_cup`, "綠色杯子"
- `cup`, "杯子"
- `juice`, "果汁"
- `water`, "瓶裝水"
- `a_carton_of_milk`, "牛奶"
- `scissors`, "剪刀"
- `drawer` , "抽屜"
- `remote_control`, "遙控器"
- `book`    , "書"
- `banana`  , "香蕉"
- `apple`   , "蘋果"
- `medicine jar`  , "藥罐"
朗讀句子要用的物件名稱也請盡量使用上述對照表的名稱的中文，若照片中有其他物件也請盡量描述出來。
畫面中一定有物品，盡量形容
位置回覆的中文是
- location 0: "目前位置"
- location 1: "小桌子"
- location 2: "廚房餐桌"
- location 3: "床旁邊桌子"
- location 4: "沙發前桌子"   
- location 5: "黑色桌子"
- location 6: "客廳長桌子"
- location 7: "客廳長桌子"
JSON 輸出格式必須是：
{{
  "objects": [
    {{"name": "apple", "count": 1}},
    {{"name": "cup", "count": 1}}
  ],
  "speech_text": "我現在來到小桌子，看到上面有一顆蘋果、一個杯子。"
}}
""".strip()

        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": user_prompt},
                            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}},
                        ],
                    },
                ],
                temperature=0.2,
                response_format={"type": "json_object"},
            )
        except Exception as error:
            rospy.logerr(f"[ScanTableObjects] OpenAI VLM 呼叫失敗: {error}")
            return None

        raw_content = response.choices[0].message.content
        try:
            return json.loads(raw_content)
        except Exception:
            rospy.logerr(f"[ScanTableObjects] VLM 回覆非 JSON: {raw_content}")
            return None

    def _normalize_objects(self, objects):
        normalized = []
        if not isinstance(objects, list):
            return normalized

        for item in objects:
            if isinstance(item, dict):
                name = str(item.get("name", "")).strip().lower()
                count = item.get("count", 1)
            else:
                name = str(item).strip().lower()
                count = 1

            if not name:
                continue

            try:
                count = int(count)
            except (TypeError, ValueError):
                count = 1

            if count < 1:
                count = 1

            normalized.append({"name": name, "count": count})

        return normalized

    def _build_default_speech(self, location_name, object_entries):
        if not object_entries:
            return f"我掃描了 {location_name}，目前沒有看到明顯物品。"

        parts = []
        for item in object_entries:
            parts.append(f"{item['count']}個{item['name']}")
        objects_text = "、".join(parts)
        return f"我掃描了 {location_name}，目前看到 {objects_text}。"