#!/usr/bin/env python3
import json
import rospy
from std_msgs.msg import String, Int32

from actions.pick_action import PickAction
from actions.place_action import PlaceAction
from actions.pour import PourAction
from actions.open_drawer import openDrawerAction
from actions.store_on_tray import StoreOnTrayAction
from actions.retrieve_from_tray import RetrieveFromTrayAction
from actions.handover import HandoverAction
from actions.water_dispenser import waterDispenserAction
from actions.scantableobjects import ScanTableObjects

# 建立動作字串與 Class 的映射表
ACTION_REGISTRY = {
    "PICK": PickAction,
    "PLACE": PlaceAction,
    "POUR": PourAction,
    "OPEN_DRAWER": openDrawerAction,
    # "HANDOVER": HandoverAction,
    "STORE_ON_TRAY": StoreOnTrayAction,
    "RETRIEVE_FROM_TRAY": RetrieveFromTrayAction,
    "HANDOVER": HandoverAction,
    # "WAIT": WaitAction,
    "WATER_DISPENSER": waterDispenserAction,
    "SCAN_TABLE_OBJECTS": ScanTableObjects,
}


def normalize_task_fields(task_data: dict) -> dict:
    normalized = dict(task_data)

    object_name = normalized.get("object") or normalized.get("target_object")
    if object_name:
        normalized.setdefault("object", object_name)
        normalized.setdefault("target_object", object_name)

    hand_name = normalized.get("hand") or normalized.get("hand_used")
    if hand_name:
        normalized.setdefault("hand", hand_name)
        normalized.setdefault("hand_used", hand_name)

    return normalized


def dispatch_and_execute(task_data: dict) -> bool:
    """
    接收任務字典，自動實例化對應的 Action Class 並執行。
    """
    action_type = task_data.get("action_type")

    # 從字典中找出對應的 Class
    action_class = ACTION_REGISTRY.get(action_type)

    if not action_class:
        rospy.logerr(f"[Dispatcher] 未知的動作類型: {action_type}")
        return False

    try:
        # 實例化該動作 (傳入任務參數)
        action_instance = action_class(task_data)

        # 執行動作
        return bool(action_instance.execute())
    except Exception as error:
        rospy.logerr(f"[Dispatcher] 執行 {action_type} 時發生崩潰: {error}")
        return False


class ActionDispatcherNode:
    def __init__(self):
        rospy.init_node("action_dispatcher")

        self.status_pub = rospy.Publisher("/robot_status", Int32, queue_size=10)
        self.current_task_sub = rospy.Subscriber("/current_task", String, self.current_task_callback)

        rospy.loginfo("[Dispatcher] Ready. Waiting for /current_task ...")

    def current_task_callback(self, msg: String):
        try:
            task_data = json.loads(msg.data)
            if not isinstance(task_data, dict):
                rospy.logerr("[Dispatcher] current_task JSON 格式錯誤，需為 dict")
                return
        except Exception as error:
            rospy.logerr(f"[Dispatcher] current_task JSON Parse Error: {error}")
            return

        task_data = normalize_task_fields(task_data)

        task_id = task_data.get("global_id", "N/A")
        action_type = task_data.get("action_type", "UNKNOWN")
        location_id = task_data.get("location_id", "N/A")

        rospy.loginfo(f"[Dispatcher] 📥 Received Task: {task_id} ({action_type} @ Loc {location_id})")

        # 告知系統目前進入執行狀態
        self.status_pub.publish(Int32(data=1))

        success = dispatch_and_execute(task_data)
        if success:
            rospy.loginfo(f"[Dispatcher] ✅ Task {task_id} finished")
        else:
            rospy.logwarn(f"[Dispatcher] ❌ Task {task_id} failed")

        # 無論成功/失敗都回到閒置，讓 execution_node 可派發下一筆
        self.status_pub.publish(Int32(data=0))


if __name__ == "__main__":
    try:
        ActionDispatcherNode()
        rospy.spin()
    except rospy.ROSInterruptException:
        pass