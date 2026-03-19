import rospy

from .base_action import BaseAction


class PickAction(BaseAction):
    """PICK 動作執行器：負責取得目標物座標並銜接後續夾取流程。"""

    def execute(self) -> bool:
        # 1) 解析任務參數
        obj = self._resolve_object_name()
        hand = self._resolve_hand_name()
        location = self._resolve_location_id()
        camera_id = self._resolve_camera_id(default=0)

        # 2) 基本防呆：沒有目標物就無法執行 PICK
        if not obj:
            rospy.logerr(f"[{self.action_type}] 缺少物件名稱，請確認 task 內有 object/target_object")
            return False

        rospy.loginfo(f"[{self.action_type}] 開始執行 PICK: 使用 {hand} 手抓取 {location} 的 {obj}")

        # 3) 向視覺 service 取得物件表面座標（camera frame）
        result = self._request_object_xyz(obj, camera_id=camera_id)
        if result is None:
            return False

        # 4) 視需求轉換為世界座標（供手臂規劃使用）
        x, y, z = result.x, result.y, result.z
        world_x, world_y, world_z = self._to_world_xyz([x, y, z], camera_id=camera_id)
        rospy.loginfo(
            f"[{self.action_type}] 取得 {obj} 座標: x={x:.2f}, y={y:.2f}, z={z:.2f} mm | "
            f"R={result.radius:.2f} mm | frame={result.frame_id}"
        )
        rospy.loginfo(
            f"[{self.action_type}] 轉換後世界座標: x={world_x:.2f}, y={world_y:.2f}, z={world_z:.2f} mm"
        )
        pre_dis = 100.0
        # 5) 後續要串接的實體動作（你直接在這裡寫 flow）
        # 先去距它它100mm
        self.robot_control.pos_single_move(hand, -90 , 0, 0, world_x - pre_dis, world_y, world_z)
        # 參考：
        # self.robot_control.single_arm_initial_position(hand)
        # self.robot_control.pos_single_move(hand, ox_deg, oy_deg, oz_deg, world_x, world_y, world_z)
        # self.robot_control.close_gripper(hand)

        rospy.sleep(2.0)
        rospy.loginfo(f"[{self.action_type}] PICK 執行完畢！")
        return True