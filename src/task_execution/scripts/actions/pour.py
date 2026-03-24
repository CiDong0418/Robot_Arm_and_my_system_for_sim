import rospy
import math

from .base_action import BaseAction


class PourAction(BaseAction):
    """POUR 動作執行器：依照 PICK 記錄與桌面高度差完成傾倒流程。"""

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
            rospy.logerr(f"[{self.action_type}] 缺少 hand/hand_used，無法執行 POUR")
            return False
        if not obj_raw:
            rospy.logerr(f"[{self.action_type}] 缺少 object/target_object，無法執行 POUR")
            return False
        obj = str(obj_raw).strip().lower()
        if not obj:
            rospy.logerr(f"[{self.action_type}] object/target_object 為空字串，無法執行 POUR")
            return False


        rospy.loginfo(f"[{self.action_type}] 開始執行 POUR: 使用 {hand} 手傾倒 {location} 的 {obj}")

        
        # obj_raw = "target_object": "milk -> cup"
        pour_obj , catch_obj = obj.split("->")
        pour_obj = pour_obj.strip()
        catch_obj = catch_obj.strip()

        target_drop_z = self._compute_target_drop_z(catch_obj, location)
        if target_drop_z is None:
            return False

        if catch_obj == self.arm_have_object["right"] :
            # 先放下來
            table_x = 500.0
            table_y = 0.0
            target_z = target_drop_z
            right_hand_initial_x = 420.0
            right_hand_initial_y = -130.0
            right_hand_initial_z = -130.0
            put_hand = "right"

            if catch_obj == "cup":
                move_out = 70.0
                self.arm_pos_move_horizontal(put_hand, table_x, table_y, target_z + 80)
                self.arm_pos_move_horizontal(put_hand, table_x, table_y, target_z)
                self.open_gripper(put_hand)

                # if hand == "right":
                self.arm_pos_move_horizontal(put_hand, table_x - move_out, table_y - move_out, target_z + 50)
                mid_x = ((table_x - move_out) - right_hand_initial_x) / 2 + right_hand_initial_x
                mid_y = ((table_y - move_out) - right_hand_initial_y) / 2 + right_hand_initial_y
                mid_z = ((target_z + 50) - right_hand_initial_z) / 2 + right_hand_initial_z
                self.arm_pos_move_horizontal(put_hand, mid_x, mid_y, mid_z)                    
                self.right_arm_initial_position()
                
                self.arm_have_object[put_hand] = None
        elif catch_obj == self.arm_have_object["left"] :
            table_x = 500.0
            table_y = 0.0
            target_z = target_drop_z
            left_hand_initial_x = 420.0
            left_hand_initial_y = 130.0
            left_hand_initial_z = -130.0
            put_hand = "left"
            if catch_obj == "cup":
                move_out = 70.0
                self.arm_pos_move_horizontal(put_hand, table_x, table_y, target_z + 80)
                self.arm_pos_move_horizontal(put_hand, table_x, table_y, target_z)
                self.open_gripper(put_hand)

                # elif hand == "left":
                self.arm_pos_move_horizontal(put_hand, table_x - move_out, table_y + move_out, target_z + 50)
                mid_x = ((table_x - move_out) - left_hand_initial_x) / 2 + left_hand_initial_x
                mid_y = ((table_y + move_out) - left_hand_initial_y) / 2 + left_hand_initial_y
                mid_z = ((target_z + 50) - left_hand_initial_z) / 2 + left_hand_initial_z
                self.arm_pos_move_horizontal(put_hand, mid_x, mid_y, mid_z)
                self.left_arm_initial_position()
                
                self.arm_have_object[put_hand] = None
        if pour_obj == self.arm_have_object["right"] :
            #  傾倒 
            table_x = 500.0
            table_y = 0.0
            target_z = target_drop_z
            move_xy = 100.0
            move_z = -80.0
            put_hand = "right"
            self.arm_pos_move_horizontal(put_hand, table_x + move_xy/2, table_y - move_xy, move_z)
            self.right_arm_all_degree_move(0.0, (180.0-45.0), -80, table_x + move_xy/2, table_y - move_xy , move_z ) # 傾斜 45 度
            self.arm_pos_move_horizontal(put_hand, table_x + move_xy/2, table_y - move_xy , move_z)
            self.right_arm_initial_position()  # 回到初始位置
        elif pour_obj == self.arm_have_object["left"] :
            table_x = 500.0
            table_y = 0.0
            target_z = target_drop_z
            move_xy = 100.0
            move_z = -80.0
            put_hand = "left"
            self.arm_pos_move_horizontal(put_hand, table_x + move_xy/2, table_y + move_xy, move_z)
            self.left_arm_all_degree_move(0.0, (180.0-45.0), 80, table_x + move_xy/2, table_y + move_xy , move_z ) # 傾斜 45 度
            self.arm_pos_move_horizontal(put_hand, table_x + move_xy/2, table_y + move_xy , move_z)
            self.left_arm_initial_position()  # 回到初始位置
            



       
        
        else:
            rospy.logwarn(f"[{self.action_type}] 尚未定義物件 {obj} 的 POUR 動作，先略過動作控制")
            return False    