import rospy

from .base_action import BaseAction


class HandoverAction(BaseAction):
    """HANDOVER 動作執行器：在左右手之間轉移物品。"""

    def execute(self) -> bool:
        from_hand = self.task_data.get("from_hand") or self.task_data.get("hand_used")
        to_hand = self.task_data.get("to_hand")

        if not from_hand or not to_hand:
            rospy.logerr(f"[{self.action_type}] 缺少 from_hand/to_hand，無法執行 HANDOVER")
            return False

        from_hand = self._normalize_hand(from_hand)
        to_hand = self._normalize_hand(to_hand)

        if from_hand == to_hand:
            rospy.logerr(f"[{self.action_type}] from_hand 與 to_hand 相同，無法執行 HANDOVER")
            return False

        if self.arm_have_object.get(from_hand) is None:
            rospy.logerr(f"[{self.action_type}] {from_hand} 手沒有物品，無法 HANDOVER")
            return False

        if self.arm_have_object.get(to_hand) is not None:
            rospy.logerr(f"[{self.action_type}] {to_hand} 手已滿，無法 HANDOVER")
            return False

        obj = self.arm_have_object[from_hand]
        rospy.loginfo(f"[{self.action_type}] HANDOVER: {from_hand} -> {to_hand} ({obj})")

        # 目前先更新狀態，不實作實體控制流程。
        self.arm_have_object[from_hand] = None
        self.arm_have_object[to_hand] = obj

        return True

    @staticmethod
    def _normalize_hand(hand_name):
        if not isinstance(hand_name, str):
            return hand_name

        key = hand_name.strip().lower()
        if key in ["left_arm", "left"]:
            return "left"
        if key in ["right_arm", "right"]:
            return "right"
        return hand_name
