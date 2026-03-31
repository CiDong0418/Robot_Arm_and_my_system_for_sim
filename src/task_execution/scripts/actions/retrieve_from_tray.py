import rospy

from .base_action import BaseAction


class RetrieveFromTrayAction(BaseAction):
    """RETRIEVE FROM TRAY 動作執行器：從胸前托盤取回物品。"""

    def execute(self) -> bool:
        hand = self._resolve_hand_name()
        location = self._resolve_location_id()
        obj_raw = self._resolve_object_name()

        if not hand:
            rospy.logerr(f"[{self.action_type}] 缺少 hand/hand_used，無法執行 RETRIEVE_FROM_TRAY")
            return False

        if self.tray_memory is None:
            self.tray_memory = []

        if not obj_raw:
            rospy.logerr(f"[{self.action_type}] 缺少 object/target_object，無法執行 RETRIEVE_FROM_TRAY")
            return False

        obj = str(obj_raw).strip().lower()
        if not obj:
            rospy.logerr(f"[{self.action_type}] 物件名稱為空字串，無法執行 RETRIEVE_FROM_TRAY")
            return False

        if obj not in self.tray_memory:
            rospy.logerr(f"[{self.action_type}] 托盤上找不到 {obj}，無法取回")
            return False

        if self.arm_have_object.get(hand) is not None:
            rospy.logerr(f"[{self.action_type}] {hand} 手已滿，無法取回托盤物品")
            return False

        rospy.loginfo(f"[{self.action_type}] 開始執行 RETRIEVE_FROM_TRAY: 使用 {hand} 手取回 {obj}")

        # 目前不做實體抓取流程，只更新內部狀態。
        self.tray_memory.remove(obj)
        self.arm_have_object[hand] = obj

        if location is not None:
            self.now_location_id["now"] = location

        rospy.loginfo(f"[{self.action_type}] RETRIEVE_FROM_TRAY 執行完畢！")
        return True
