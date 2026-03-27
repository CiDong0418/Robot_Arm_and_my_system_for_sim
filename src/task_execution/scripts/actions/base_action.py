from abc import ABC, abstractmethod
from typing import Sequence
import time
import threading
from types import SimpleNamespace

import rospy
import rostopic
from std_msgs.msg import String, Float32, Float32MultiArray, Int32
from geometry_msgs.msg import PointStamped

from .action_runtime import get_action_runtime


class BaseAction(ABC):
    """
    所有機器人動作的基礎父類別 (Abstract Base Class)。

    備註：
    - 各 Action 子類別只需要關注自身流程（execute）。
    - 欄位解析、座標服務呼叫、座標轉換等共用功能統一放在這裡。
    """
    # Class Attribute
    pick_shared_memory = {
        # "object": None,
        # "pick_xyz": [0.0, 0.0, 0.0],
        # "pick_table_id": None
    }

    arm_have_object = {
        "left": None,
        "right": None,
    }

    now_location_id = -1

    def __init__(self, task_data: dict):
        """初始化每個動作共用的任務資料與執行介面。"""
        self.task_data = task_data
        self.action_type = task_data.get("action_type", "UNKNOWN")
        self.global_id = task_data.get("global_id", "N/A")
        self.robot_control, self.camera_transfer = get_action_runtime()
        self.table_heights = {
            1: 709.0,
            2: 709.0,
            3: 850.0
        }
        # 0~12
        self.location_xyoz_m = {
            0: (0.0, 0.0, 0.0),
            1: (0.0, 0.0, 0.0),
            2: (0.0, 0.0, 0.0),
            3: (0.0, 0.0, 0.0),
            4: (0.0, 0.0, 0.0),
            5: (0.0, 0.0, 0.0),
            6: (0.0, 0.0, 0.0),
            7: (0.0, 0.0, 0.0),
            8: (0.0, 0.0, 0.0),
            9: (0.0, 0.0, 0.0),
            10: (0.0, 0.0, 0.0),
            11: (0.0, 0.0, 0.0),
            12: (0.0, 0.0, 0.0),
        }



        self._anna_move_pub = rospy.Publisher("/anna_move", Float32MultiArray, queue_size=10)
        self._task_done_cv = threading.Condition()
        self._task_done_seq = 0
        self._task_done_last_value = None
        self._task_done_sub = None
        self._init_task_done_subscriber()

    def _init_task_done_subscriber(self):
        """根據 /task_done 真實型別建立 subscriber，避免型別不符收不到訊息。"""
        task_done_topic = rospy.get_param("/task_execution/task_done_topic", "/task_done")
        msg_class = None

        try:
            msg_class, _, _ = rostopic.get_topic_class(task_done_topic, blocking=False)
        except Exception as error:
            rospy.logwarn(f"[{self.action_type}] 偵測 {task_done_topic} 型別失敗，改用 Int32: {error}")

        if msg_class is None:
            msg_class = Int32

        self._task_done_sub = rospy.Subscriber(task_done_topic, msg_class, self._task_done_cb, queue_size=10)

    def _task_done_cb(self, msg):
        try:
            raw_value = getattr(msg, "data", msg)
            if isinstance(raw_value, bool):
                value = 1.0 if raw_value else 0.0
            else:
                value = float(raw_value)
        except (TypeError, ValueError):
            text_value = str(getattr(msg, "data", "")).strip()
            value = 1.0 if text_value == "1" else 0.0

        with self._task_done_cv:
            self._task_done_seq += 1
            self._task_done_last_value = value
            self._task_done_cv.notify_all()

    def move_base_and_wait(self, x, y, oz, timeout_sec=None, wait_subscriber_sec=1.5):
        """
        發送底盤導航目標到 /anna_move，並阻塞直到收到新的 /task_done == 1。

        參數：
        - x, y, oz: 要傳給 /anna_move 的三個數值。
        - timeout_sec: 等待秒數；None 代表無限等待。
        - wait_subscriber_sec: 發送前等待 /anna_move 有 subscriber 的最長秒數。

        回傳：
        - True: 收到新的 /task_done == 1。
        - False: ROS 關閉或等待逾時。
        """
        target = Float32MultiArray(data=[float(x), float(y), float(oz)])

        wait_deadline = time.time() + max(0.0, float(wait_subscriber_sec))
        while (
            self._anna_move_pub.get_num_connections() == 0
            and time.time() < wait_deadline
            and not rospy.is_shutdown()
        ):
            rospy.sleep(0.05)

        with self._task_done_cv:
            start_seq = self._task_done_seq

        self._anna_move_pub.publish(target)
        rospy.loginfo(
            f"[{self.action_type}] 已發送 /anna_move: x={float(x):.3f}, y={float(y):.3f}, oz={float(oz):.3f}，等待 /task_done=1"
        )

        deadline = None if timeout_sec is None else (time.time() + max(0.0, float(timeout_sec)))
        with self._task_done_cv:
            while not rospy.is_shutdown():
                if self._task_done_seq > start_seq and self._task_done_last_value is not None:
                    if abs(float(self._task_done_last_value) - 1.0) < 1e-6:
                        rospy.loginfo(f"[{self.action_type}] 收到 /task_done=1，導航完成")
                        return True

                if deadline is None:
                    self._task_done_cv.wait(timeout=0.2)
                    continue

                remaining = deadline - time.time()
                if remaining <= 0.0:
                    break
                self._task_done_cv.wait(timeout=min(0.2, remaining))

        rospy.logwarn(f"[{self.action_type}] 等待 /task_done=1 失敗（逾時或 ROS 關閉）")
        return False

    def _resolve_first_value(self, *keys, default=None):
        """
        依照 keys 優先順序取第一個可用欄位值。

        - 會略過 None 與空字串。
        - 若都找不到，回傳 default。
        """
        for key in keys:
            value = self.task_data.get(key)
            if value is None:
                continue
            if isinstance(value, str):
                value = value.strip()
                if not value:
                    continue
            return value
        return default

    def _resolve_object_name(self):
        """取得目標物名稱，兼容 object/target_object/item_name 欄位。"""
        return self._resolve_first_value("object", "target_object", "item_name")

    def _resolve_hand_name(self):
        """
        取得手臂名稱並做標準化。

        例：left_arm -> left、right_arm -> right。
        """
        hand_name = self._resolve_first_value("hand", "hand_used")
        if not isinstance(hand_name, str):
            return hand_name

        hand_map = {
            "left_arm": "left",
            "right_arm": "right",
            "left": "left",
            "right": "right",
        }
        return hand_map.get(hand_name.lower(), hand_name) #return type is str(hand_name)

    def _resolve_location_id(self):
        """取得位置欄位，兼容 location_id/location。"""
        return self._resolve_first_value("location_id", "location")

    def _resolve_pick_context(self, object_name):
        """從 pick_shared_memory 取出指定物件的 PICK 記錄。"""
        pick_shared_memory = getattr(self, "pick_shared_memory", None)
        if not isinstance(pick_shared_memory, dict):
            rospy.logerr(f"[{self.action_type}] 缺少 pick_shared_memory，無法讀取 PICK 記錄")
            return None

        object_key = str(object_name).strip().lower()
        if object_key not in pick_shared_memory:
            rospy.logerr(f"[{self.action_type}] 記憶體中找不到 {object_name} 的拿取紀錄")
            return None

        return pick_shared_memory[object_key]

    def _resolve_camera_id(self, default=0) -> int:
        """
        取得 camera_id 並轉成 int。

        若欄位格式錯誤，會記錄警告並回退到 default。
        """
        camera_id = self.task_data.get("camera_id", default)
        try:
            return int(camera_id)
        except (TypeError, ValueError):
            rospy.logwarn(f"[{self.action_type}] camera_id 格式錯誤 ({camera_id})，改用預設值 {default}")
            return int(default)

    def _resolve_object_xyz_service_name(self, camera_id=0) -> str:
        """
        根據 camera_id 解析要呼叫的座標服務名稱。

        解析順序：
        1) /task_execution/object_xyz_service_name_by_camera/<camera_id>
        2) /task_execution/object_xyz_service_name_by_camera (dict, key 可為字串或數字)
        3) /task_execution/object_xyz_service_name (預設)
        """
        default_service = rospy.get_param(
            "/task_execution/object_xyz_service_name",
            "/head_detection/get_object_xyz",
        )

        service_name = rospy.get_param(f"/task_execution/object_xyz_service_name_by_camera/{camera_id}", "")
        if isinstance(service_name, str) and service_name.strip():
            return service_name.strip()

        service_map = rospy.get_param("/task_execution/object_xyz_service_name_by_camera", {})
        if isinstance(service_map, dict):
            mapped = service_map.get(str(camera_id), service_map.get(camera_id))
            if isinstance(mapped, str) and mapped.strip():
                return mapped.strip()

        return default_service

    def _resolve_object_xyz_topic_prefix(self, camera_id=0) -> str:
        """
        根據 camera_id 解析偵測 topic 前綴。

        解析順序：
        1) /task_execution/object_xyz_topic_prefix_by_camera/<camera_id>
        2) /task_execution/object_xyz_topic_prefix_by_camera (dict)
        3) /task_execution/object_xyz_topic_prefix (預設 /head_detection)
        """
        default_prefix = rospy.get_param(
            "/task_execution/object_xyz_topic_prefix",
            "/head_detection",
        )

        prefix = rospy.get_param(f"/task_execution/object_xyz_topic_prefix_by_camera/{camera_id}", "")
        if isinstance(prefix, str) and prefix.strip():
            return prefix.strip()

        prefix_map = rospy.get_param("/task_execution/object_xyz_topic_prefix_by_camera", {})
        if isinstance(prefix_map, dict):
            mapped = prefix_map.get(str(camera_id), prefix_map.get(camera_id))
            if isinstance(mapped, str) and mapped.strip():
                return mapped.strip()

        return default_prefix

    def _request_object_xyz_via_topic(self, object_name: str, camera_id=0):
        prefix = self._resolve_object_xyz_topic_prefix(camera_id=camera_id)
        timeout_sec = float(rospy.get_param("/task_execution/object_xyz_timeout_sec", 8.0))

        target_topic = f"{prefix}/target"
        xyz_topic = f"{prefix}/xyz"
        radius_topic = f"{prefix}/radius"
        status_topic = f"{prefix}/status"

        state = {
            "xyz": None,
            "radius": 0.0,
            "status": None,
        }
        done_event = threading.Event()

        def _cb_xyz(msg: PointStamped):
            state["xyz"] = (
                float(msg.point.x),
                float(msg.point.y),
                float(msg.point.z),
                msg.header.frame_id,
            )

        def _cb_radius(msg: Float32):
            state["radius"] = float(msg.data)

        def _cb_status(msg: String):
            state["status"] = msg.data.strip()
            done_event.set()

        sub_xyz = rospy.Subscriber(xyz_topic, PointStamped, _cb_xyz, queue_size=1)
        sub_radius = rospy.Subscriber(radius_topic, Float32, _cb_radius, queue_size=1)
        sub_status = rospy.Subscriber(status_topic, String, _cb_status, queue_size=1)
        target_pub = rospy.Publisher(target_topic, String, queue_size=1)

        try:
            rospy.sleep(0.1)
            target_pub.publish(String(data=object_name))

            if not done_event.wait(timeout=timeout_sec):
                rospy.logerr(f"[{self.action_type}] topic 模式等待 {status_topic} 逾時")
                return None

            status_text = state["status"] or "FAIL | no status"
            if not status_text.startswith("OK"):
                rospy.logerr(f"[{self.action_type}] topic 模式辨識失敗: {status_text}")
                return None

            # topic 之間沒有跨 topic 順序保證：status 可能比 xyz 先到
            # 這裡給一個短暫緩衝等待 xyz，避免偶發競態造成誤判失敗
            xyz_wait_deadline = time.time() + min(0.8, timeout_sec)
            while state["xyz"] is None and time.time() < xyz_wait_deadline and not rospy.is_shutdown():
                rospy.sleep(0.02)

            if state["xyz"] is None:
                rospy.logerr(f"[{self.action_type}] topic 模式缺少 xyz 資料（status={status_text}）")
                return None

            x_value, y_value, z_value, frame_id = state["xyz"]
            return SimpleNamespace(
                success=True,
                message=status_text,
                x=x_value,
                y=y_value,
                z=z_value,
                radius=float(state["radius"]),
                frame_id=frame_id,
            )
        finally:
            sub_xyz.unregister()
            sub_radius.unregister()
            sub_status.unregister()

    def _request_object_xyz(self, object_name: str, camera_id=0):
        """
        呼叫視覺服務取得物件座標。

        參數：
        - object_name: 要查詢的目標物名稱。
        - camera_id: 用來選擇要呼叫哪一個座標 service。

        回傳：
        - 成功時回傳 GetObjectXYZResponse。
        if not target_name:
            return GetObjectXYZResponse(
                success=False,
                message="target_name is empty",
                x=0.0,
                y=0.0,
                z=0.0,
                radius=0.0,
                frame_id="",
            )
        - 失敗時回傳 None。
        """
        if not object_name:
            rospy.logerr(f"[{self.action_type}] object_name 為空，無法呼叫座標服務")
            return None

        transport = str(rospy.get_param("/task_execution/object_xyz_transport", "topic")).strip().lower()
        if transport == "topic":
            return self._request_object_xyz_via_topic(object_name=object_name, camera_id=camera_id)

        service_name = self._resolve_object_xyz_service_name(camera_id=camera_id)
        timeout_sec = float(rospy.get_param("/task_execution/object_xyz_timeout_sec", 8.0))

        try:
            rospy.wait_for_service(service_name, timeout=timeout_sec)
        except rospy.ROSException:
            rospy.logerr(f"[{self.action_type}] 等待 service {service_name} 逾時")
            return None

        try:
            from image.srv import GetObjectXYZ, GetObjectXYZRequest
        except Exception as error:
            rospy.logerr(f"[{self.action_type}] 載入 GetObjectXYZ service 介面失敗: {error}")
            return None

        try:
            service_proxy = rospy.ServiceProxy(service_name, GetObjectXYZ)
            request = GetObjectXYZRequest(target_name=object_name, timeout_sec=timeout_sec)
            response = service_proxy(request)
        except rospy.ServiceException as error:
            rospy.logerr(f"[{self.action_type}] 呼叫 {service_name} 失敗: {error}")
            return None

        if not response.success:
            rospy.logerr(f"[{self.action_type}] 物件 '{object_name}' 座標取得失敗: {response.message}")
            return None

        return response  # return type is GetObjectXYZResponse

    def _to_world_xyz(self, camera_xyz_mm: Sequence[float], camera_id=0):
        """
        將相機座標（mm）轉為世界座標（mm）。

        - 若關閉 /task_execution/use_camera_transfer，直接回傳原始座標。
        - 若轉換失敗，會記錄警告並回傳原始座標。
        """
        camera_xyz_list = list(camera_xyz_mm)
        if len(camera_xyz_list) < 3:
            rospy.logwarn(f"[{self.action_type}] camera_xyz_mm 維度不足，改用原始資料: {camera_xyz_list}")
            return camera_xyz_list

        camera_xyz_list = [
            float(camera_xyz_list[0]),
            float(camera_xyz_list[1]),
            float(camera_xyz_list[2]),
        ]

        use_camera_transfer = bool(rospy.get_param("/task_execution/use_camera_transfer", True))
        if not use_camera_transfer:
            return camera_xyz_list

        try:
            world_xyz = self.camera_transfer.list_transform_points(camera_id, camera_xyz_list)
            if world_xyz and len(world_xyz) >= 3:
                return [float(world_xyz[0]), float(world_xyz[1]), float(world_xyz[2])]
        except Exception as error:
            rospy.logwarn(f"[{self.action_type}] camera_transfer 轉換失敗，改用原始座標: {error}")

        return camera_xyz_list

    def right_arm_initial_position(self):
        """右手回到初始位置的快捷方式。"""
        self.robot_control.pos_single_move("right", 0.0, 140.0, 0.0, 420.0, -130.0, -130.0)
        
    
    def left_arm_initial_position(self):
        """左手回到初始位置的快捷方式。"""
        self.robot_control.pos_single_move("left", -180.0, 35.0, 0.0, 420.0, 130.0, -130.0)
    
    def both_arms_initial_position(self):
        self.robot_control.initial_position()  # 移動到初始位置
    
    def open_gripper(self, arm):
        self.robot_control.open_gripper(arm)

    def close_gripper(self, arm):
        self.robot_control.close_gripper(arm)

    def degree_gripper_control(self, arm, angle):
        self.robot_control.gripper_control(arm, angle)

    def arm_pos_move_horizontal(self, arm, x_mm, y_mm, z_mm):
        if arm == "left":
            if x_mm > 200 and x_mm < 350 and y_mm > -150 and y_mm < 150: # 平台區域限制
                self.robot_control.pos_single_move("left", -180, 0.0, 0.0, x_mm, y_mm, z_mm)
            elif y_mm <= 250 and x_mm < 580: # 左手前方限制65
                self.robot_control.pos_single_move("left", -180, 25.0, 0.0, x_mm, y_mm, z_mm)
            elif y_mm <= 250 and x_mm < 680: # 左手前方限制45
                self.robot_control.pos_single_move("left", -180, 45.0, 0.0, x_mm, y_mm, z_mm)
            # elif y_mm < -200 and y_mm > -400 : # 左手極限位置22.5
            #     slope = ((-400) - (-200)) / (640 - 720) # y = mx + b
            #     line_y = slope * (x_mm - 720) - 200
            #     if y_mm <= line_y:
            #         robot_control.pos_single_move("left", -180+67.5, 35, 0.0, x_mm, y_mm, z_mm)
            else:
                rospy.logwarn(f"[{self.action_type}] 目標位置超出左手可達範圍，請調整座標: x={x_mm}, y={y_mm}, z={z_mm}")
                time.sleep(2.0)
        elif arm == "right":
            if x_mm > 200 and x_mm < 350 and y_mm > -150 and y_mm < 150: # 平台區域限制
                self.robot_control.pos_single_move("right", 0.0, (180), 0.0, x_mm, y_mm, z_mm)
            elif y_mm >= -250 and x_mm < 580: # 右手前方限制65
                self.robot_control.pos_single_move("right", 0.0, (180-25), 0.0, x_mm, y_mm, z_mm)
            elif y_mm >= -200 and x_mm < 700: # 右手前方限制45
                self.robot_control.pos_single_move("right", 0.0, (180-45), 0.0, x_mm, y_mm, z_mm)
            elif y_mm < -200 and y_mm > -400 : # 右手極限位置22.5
                slope = ((-400) - (-200)) / (640 - 720) # y = mx + b
                line_y = slope * (x_mm - 720) - 200
                if y_mm <= line_y:
                    self.robot_control.pos_single_move("right", 0.0, (180-67.5), 0.0, x_mm, y_mm, z_mm)
            else:
                rospy.logwarn(f"[{self.action_type}] 目標位置超出右手可達範圍，請調整座標: x={x_mm}, y={y_mm}, z={z_mm}")
                time.sleep(2.0) 
            
    
    def arm_pos_move_vertical(self, arm, x_mm, y_mm, z_mm):
        if arm == "right":
            if x_mm > 200 and x_mm < 550 and y_mm > -300 and y_mm < -20 and z_mm > -350 and z_mm < -150: # 右手垂直區域限制
                self.robot_control.pos_single_move("right", 95.0, 0.0, -90.0, x_mm, y_mm, z_mm)
        elif arm == "left":
            if x_mm > 200 and x_mm < 550 and y_mm < 300 and y_mm > 20 and z_mm > -350 and z_mm < -150: # 左手垂直區域限制
                self.robot_control.pos_single_move("left", -95.0, 0.0, -90.0, x_mm, y_mm, z_mm)
        else:
            rospy.logwarn(f"[{self.action_type}] 目標位置超出可達範圍，請調整座標: x={x_mm}, y={y_mm}, z={z_mm}")
            time.sleep(2.0)

    def right_arm_all_degree_move(self, ox, oy, oz, x_mm, y_mm, z_mm):
        self.robot_control.pos_single_move("right", ox, oy, oz, x_mm, y_mm, z_mm)

    def left_arm_all_degree_move(self, ox, oy, oz, x_mm, y_mm, z_mm):
        self.robot_control.pos_single_move("left", ox, oy, oz, x_mm, y_mm, z_mm)

    def dual_arm_move(self,left_oy, left_xyz_mm,right_oy, right_xyz_mm):
        self.robot_control.pos_dual_move(
            -180.0, left_oy, 0.0,  left_xyz_mm[0], left_xyz_mm[1], left_xyz_mm[2],
             0.0, (180-right_oy), 0.0,  right_xyz_mm[0], right_xyz_mm[1], right_xyz_mm[2]
        )
    @abstractmethod
    def execute(self) -> bool:
        """
        每個子類別都必須實作這個方法。
        回傳 True 代表動作成功執行，False 代表失敗。
        """
        pass