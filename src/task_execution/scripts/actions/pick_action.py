import rospy
import math

from .base_action import BaseAction


class PickAction(BaseAction):
    """PICK 動作執行器：負責取得目標物座標並銜接後續夾取流程。"""

    def execute(self) -> bool:
        obj_raw = self._resolve_object_name()
        hand = self._resolve_hand_name()
        location = self._resolve_location_id()
        camera_id = self._resolve_camera_id(default=0)

        if not obj_raw:
            rospy.logerr(f"[{self.action_type}] 缺少物件名稱，請確認 task 內有 object/target_object")
            return False

        obj = str(obj_raw).strip().lower()
        if not obj:
            rospy.logerr(f"[{self.action_type}] 物件名稱為空字串")
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
        if obj == "green_cup":
            if hand == "right":
                if world_y > -200:
                    move_deg = 100/math.sqrt(2) # 45度移動距離
                else :
                    move_deg = 100*math.cos(math.radians(22.5))
                # 先移動到距離物件約100mm的45度位置
                self.arm_pos_move_horizontal("right",  (world_x - move_deg + result.radius ), (world_y - move_deg), world_z - 40) # 移動到指定位置                                                                                                                                    
                # 再移動到物件夾取點                    
                self.arm_pos_move_horizontal("right",   world_x + result.radius -25 , world_y -35 , world_z - 40)
                self.degree_gripper_control("right", 80) # 設定右手夾爪角度為100
                self.right_arm_initial_position() # 右手回到初始位置
                world_x = world_x - 25
                world_y = world_y - 35
                world_z = world_z - 40
            elif hand == "left":
                if world_y > 0:
                    move_deg = 100/math.sqrt(2) # 45度移動距離
                else :
                    move_deg = 100*math.cos(math.radians(22.5))
                self.arm_pos_move_horizontal("left", (world_x - move_deg + result.radius), (world_y + move_deg), world_z - 40) # 移動到指定位置                                                                                                                                    
                self.arm_pos_move_horizontal("left", world_x + result.radius -25 , world_y +35 , world_z - 40)
                self.degree_gripper_control("left", 80) # 設定左手夾爪角度為100
                self.left_arm_initial_position() # 左手回到初始位置
                
                world_x = world_x - 25
                world_y = world_y + 35
                world_z = world_z - 40

            self.arm_have_object[hand] = obj
        elif obj == "cup":
            if hand == "right":
                if world_y > -200:
                    move_deg = 100/math.sqrt(2) # 45度移動距離
                else :
                    move_deg = 100*math.cos(math.radians(22.5))
                # 先移動到距離物件約100mm的45度位置
                self.arm_pos_move_horizontal("right",  (world_x - move_deg + result.radius/2 ), (world_y - move_deg), world_z - 40) # 移動到指定位置                                                                                                                                    
                # 再移動到物件夾取點                    
                self.arm_pos_move_horizontal("right",   world_x + result.radius/2  , world_y  , world_z - 40)
                self.degree_gripper_control("right", 120) # 設定右手夾爪角度為120
                self.right_arm_initial_position() # 右手回到初始位置
                world_x = world_x - 0
                world_y = world_y - 0
                world_z = world_z - 40
            elif hand == "left":
                if world_y > 0:
                    move_deg = 100/math.sqrt(2) # 45度移動距離
                else :
                    move_deg = 100*math.cos(math.radians(22.5))
                self.arm_pos_move_horizontal("left", (world_x - move_deg + result.radius/2), (world_y + move_deg), world_z - 40) # 移動到指定位置                                                                                                                                    
                self.arm_pos_move_horizontal("left", world_x + result.radius/2  , world_y  , world_z - 40)
                self.degree_gripper_control("left", 120) # 設定左手夾爪角度為120
                self.left_arm_initial_position() # 左手回到初始位置
                
                world_x = world_x - 0
                world_y = world_y + 0
                world_z = world_z - 40

            self.arm_have_object[hand] = obj
            
        # 參考：
        # self.robot_control.single_arm_initial_position(hand)
        # self.robot_control.pos_single_move(hand, ox_deg, oy_deg, oz_deg, world_x, world_y, world_z)
        # self.robot_control.close_gripper(hand)

        elif obj == "cola" or obj == "juice" or obj == "water" or obj == "tea":
            if hand == "right":
                if world_y > -200:
                    move_deg = 100/math.sqrt(2) # 45度移動距離
                else :
                    move_deg = 100*math.cos(math.radians(22.5))
                self.arm_pos_move_horizontal("right",  (world_x - move_deg + result.radius ), (world_y - move_deg), world_z - 40) # 移動到指定位置                                                                                                                                    
                self.arm_pos_move_horizontal("right",   world_x + result.radius -35 , world_y -35 , world_z - 50)
                self.degree_gripper_control("right", 160) # 設定右手夾爪角度為160
                self.right_arm_initial_position() # 右手回到初始位置
                print("test0418:")
                print(f"world_x: {world_x}, world_y: {world_y}, world_z: {world_z}, move_deg: {move_deg}, result.radius: {result.radius}")
                world_x = world_x - 35
                world_y = world_y - 35
                world_z = world_z - 50
            elif hand == "left":
                if world_y > 0:
                    move_deg = 100/math.sqrt(2) # 45度移動距離
                else :
                    move_deg = 100*math.cos(math.radians(22.5))
                self.arm_pos_move_horizontal("left", (world_x - move_deg + result.radius), (world_y + move_deg), world_z - 40) # 移動到指定位置                                                                                                                                    
                self.arm_pos_move_horizontal("left", world_x + result.radius -35 , world_y +35 , world_z - 50)
                self.degree_gripper_control("left", 160) # 設定左手夾爪角度為160
                self.left_arm_initial_position() # 左手回到初始位置
                world_x = world_x - 35
                world_y = world_y + 35
                world_z = world_z - 50
            self.arm_have_object[hand] = obj
        else:
            rospy.logwarn(f"[{self.action_type}] 尚未定義 {obj} 的 PICK 動作，僅記錄座標")

        self.pick_shared_memory[obj] = {
            "object": obj,
            "pick_xyz": [world_x, world_y, world_z],
            "pick_table_id": location
        }

        
        rospy.loginfo(f"[{self.action_type}] PICK 執行完畢！")
        return True