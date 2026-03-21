import rospy

from .base_action import BaseAction


class PlaceAction(BaseAction):
    """PLACE 動作執行器：依照 PICK 記錄與桌面高度差完成放置流程。"""

    def _resolve_pick_context(self, object_name):
        pick_shared_memory = getattr(self, "pick_shared_memory", None)
        if not isinstance(pick_shared_memory, dict):
            rospy.logerr(f"[{self.action_type}] 缺少 pick_shared_memory，無法執行 PLACE")
            return None

        object_key = str(object_name).strip().lower()
        if object_key not in pick_shared_memory:
            rospy.logerr(f"[{self.action_type}] 記憶體中找不到 {object_name} 的拿取紀錄")
            return None

        return pick_shared_memory[object_key]

    def _compute_target_drop_z(self, object_name, drop_table_id):
        table_heights = getattr(self, "table_heights", None)
        if not isinstance(table_heights, dict):
            rospy.logerr(f"[{self.action_type}] 缺少 table_heights，無法計算放置高度")
            return None

        pick_obj_data = self._resolve_pick_context(object_name)
        if pick_obj_data is None:
            return None

        pick_xyz = pick_obj_data.get("pick_xyz")
        pick_table_id = pick_obj_data.get("pick_table_id")

        if not isinstance(pick_xyz, (list, tuple)) or len(pick_xyz) < 3:
            rospy.logerr(f"[{self.action_type}] {object_name} 的 pick_xyz 格式錯誤: {pick_xyz}")
            return None
        if pick_table_id not in table_heights or drop_table_id not in table_heights:
            rospy.logerr(
                f"[{self.action_type}] table_heights 缺少 table id: pick={pick_table_id}, drop={drop_table_id}"
            )
            return None

        pick_z = float(pick_xyz[2])
        height_diff = float(table_heights[drop_table_id]) - float(table_heights[pick_table_id])
        return pick_z + height_diff

    def execute(self) -> bool:
        hand = self._resolve_hand_name()
        location = self._resolve_location_id()
        obj_raw = self._resolve_object_name()

        if not hand:
            rospy.logerr(f"[{self.action_type}] 缺少 hand/hand_used，無法執行 PLACE")
            return False
        if not obj_raw:
            rospy.logerr(f"[{self.action_type}] 缺少 object/target_object，無法執行 PLACE")
            return False
        obj = str(obj_raw).strip().lower()
        if not obj:
            rospy.logerr(f"[{self.action_type}] 物件名稱為空字串，無法執行 PLACE")
            return False
        if location is None:
            rospy.logerr(f"[{self.action_type}] 缺少 location_id/location，無法執行 PLACE")
            return False

        rospy.loginfo(f"[{self.action_type}] 開始執行 PLACE: 使用 {hand} 手放置 {obj} 到 {location}")

        target_drop_z = self._compute_target_drop_z(obj, location)
        if target_drop_z is None:
            return False

        rospy.loginfo(f"[{self.action_type}] 計算完成，{obj} 目標放置 Z 高度: {target_drop_z:.2f}")

        table_x = 600.0
        table_y = 0.0
        target_z = target_drop_z
        right_hand_initial_x = 420.0
        right_hand_initial_y = -130.0
        right_hand_initial_z = -130.0

        if obj == "cup":
            move_out = 70.0
            self.arm_pos_move_horizontal(hand, table_x, table_y, target_z + 80)
            self.arm_pos_move_horizontal(hand, table_x, table_y, target_z)
            self.open_gripper(hand)

            if hand == "right":
                self.arm_pos_move_horizontal(hand, table_x - move_out, table_y - move_out, target_z + 50)
                mid_x = ((table_x - move_out) - right_hand_initial_x) / 2 + right_hand_initial_x
                mid_y = ((table_y - move_out) - right_hand_initial_y) / 2 + right_hand_initial_y
                mid_z = ((target_z + 50) - right_hand_initial_z) / 2 + right_hand_initial_z
                self.arm_pos_move_horizontal(hand, mid_x, mid_y, mid_z)
                self.right_arm_initial_position()
            elif hand == "left":
                self.arm_pos_move_horizontal(hand, table_x - move_out, table_y + move_out, target_z + 50)
                mid_x = ((table_x - move_out) - right_hand_initial_x) / 2 + right_hand_initial_x
                mid_y = ((table_y + move_out) - right_hand_initial_y) / 2 + right_hand_initial_y
                mid_z = ((target_z + 50) - right_hand_initial_z) / 2 + right_hand_initial_z
                self.arm_pos_move_horizontal(hand, mid_x, mid_y, mid_z)
                self.left_arm_initial_position()

        elif obj in ["cola", "juice", "water", "tea"]:
            move_out = 50.0
            self.arm_pos_move_horizontal(hand, table_x, table_y, target_z + 80)
            self.arm_pos_move_horizontal(hand, table_x, table_y, target_z)
            self.open_gripper(hand)

            if hand == "right":
                self.arm_pos_move_horizontal(hand, table_x - move_out, table_y - move_out, target_z + 50)
                mid_x = ((table_x - move_out) - right_hand_initial_x) / 2 + right_hand_initial_x
                mid_y = ((table_y - move_out) - right_hand_initial_y) / 2 + right_hand_initial_y
                mid_z = ((target_z + 50) - right_hand_initial_z) / 2 + right_hand_initial_z
                self.arm_pos_move_horizontal(hand, mid_x, mid_y, mid_z)
                self.right_arm_initial_position()
            elif hand == "left":
                self.arm_pos_move_horizontal(hand, table_x - move_out, table_y + move_out, target_z + 50)
                mid_x = ((table_x - move_out) - right_hand_initial_x) / 2 + right_hand_initial_x
                mid_y = ((table_y + move_out) - right_hand_initial_y) / 2 + right_hand_initial_y
                mid_z = ((target_z + 50) - right_hand_initial_z) / 2 + right_hand_initial_z
                self.arm_pos_move_horizontal(hand, mid_x, mid_y, mid_z)
                self.left_arm_initial_position()
        else:
            rospy.logwarn(f"[{self.action_type}] 尚未定義物件 {obj} 的 PLACE 動作，先略過動作控制")
            return False

        rospy.loginfo(f"[{self.action_type}] PLACE 執行完畢！")
        return True
