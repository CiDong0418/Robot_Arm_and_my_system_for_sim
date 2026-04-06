import rospy
import math
import time
from std_msgs.msg import String as RosString, Float32

from .base_action import BaseAction


class PickAction(BaseAction):
    """PICK 動作執行器：負責取得目標物座標並銜接後續夾取流程。"""

    def execute(self) -> bool:
        obj_raw = self._resolve_object_name()
        hand = self._resolve_hand_name()
        location = self._resolve_location_id()
        camera_id = self._resolve_camera_id(default=0)

        # 確認location是否正確
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
            # self.neck_control(15, 35) # 移動到指定位置後調整頸部角度
            # time.sleep(1.0) # 等待移動穩定
            # self.neck_control(0, 35) # 調整頸部角度回正
            # self.neck_control(-15, 35) # 調整頸部角度回正
            # time.sleep(1.0) # 等待移動穩定
            # self.neck_control(0, 35) # 調整頸部角度回正
                
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

        # elif obj == "cola" or obj == "juice" or obj == "water" or obj == "tea":
        elif  obj == "juice" or obj == "water" or obj == "tea":
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
                self.arm_pos_move_horizontal("left", world_x + result.radius -35 , world_y +35  , world_z - 50)
                self.degree_gripper_control("left", 160) # 設定左手夾爪角度為160
                self.left_arm_initial_position() # 左手回到初始位置
                world_x = world_x - 35
                world_y = world_y +35
                world_z = world_z - 50
            self.arm_have_object[hand] = obj
        
        elif obj == "small_cup":
            if hand == "left":
                self.left_arm_all_degree_move(-180.0, 40.0, 0.0, world_x -55, world_y +20, world_z - 30)
                self.left_arm_all_degree_move(-180.0, 40.0, 0.0, world_x  -35 , world_y , world_z - 30)
                self.degree_gripper_control("left", 165) # 設定左手夾爪角度為160
                self.left_arm_all_degree_move(-180.0, 40.0, 0.0, world_x  -35 , world_y , world_z )
                self.left_arm_initial_position() # 左手回到初始位置
                world_x = world_x  -35
                world_y = world_y 
                world_z = world_z - 30
                self.arm_have_object[hand] = obj

        elif obj == "cola": # 這裡先當作和 juice/water/tea 一樣處理，再調整參數讓它比較適合 cola 的大小
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
                self.arm_pos_move_horizontal("left", world_x + result.radius -20 , world_y +6 , world_z - 50) # 35 35
                self.degree_gripper_control("left", 160) # 設定左手夾爪角度為160
                self.left_arm_initial_position() # 左手回到初始位置
                world_x = world_x - 35
                world_y = world_y + 35
                world_z = world_z - 50
            self.arm_have_object[hand] = obj
        elif obj == "a_carton_of_milk":
            if hand == "right":
                # if world_y > -200:
                move_deg = 130/math.sqrt(2) # 45度移動距離
                
                self.arm_pos_move_horizontal("right",  (world_x - move_deg + result.radius ), (world_y - move_deg), world_z - 40) # 移動到指定位置                                                                                                                                    
                self.arm_pos_move_horizontal("right",   world_x + result.radius -35 , world_y -40 , world_z - 70)
                self.degree_gripper_control("right", 130) 
                self.right_arm_initial_position() # 右手回到初始位置
                print("test0418:")
                print(f"world_x: {world_x}, world_y: {world_y}, world_z: {world_z}, move_deg: {move_deg}, result.radius: {result.radius}")
                world_x = world_x - 35
                world_y = world_y - 40
                world_z = world_z - 70
            elif hand == "left":
                # if world_y > 0:
                move_deg = 130/math.sqrt(2) # 45度移動距離
                
                self.arm_pos_move_horizontal("left", (world_x - move_deg + result.radius), (world_y + move_deg), world_z - 40) # 移動到指定位置                                                                                                                                    
                self.arm_pos_move_horizontal("left", world_x + result.radius -35 , world_y +40 , world_z - 70)
                self.degree_gripper_control("left", 130) # 設定左手夾爪角度為160
                self.left_arm_initial_position() # 左手回到初始位置
                world_x = world_x - 35
                world_y = world_y + 40
                world_z = world_z - 70
            self.arm_have_object[hand] = obj

        elif obj == "scissors":
            if hand == "right":
                ratio = (result.radius - 41.0) / (97.255 - 41) # 剪刀的長寬
                print(f"test0418: scissors ratio={ratio}")
                if ratio < 0 or ratio > 1:
                    rospy.logwarn(f"[{self.action_type}] scissors radius {result.radius} 超出預期範圍，無法正確計算夾取角度，請確認視覺結果是否合理")
                    ratio = max(0, min(1, ratio)) # 強制限制在0到1之間
                theta_rad = math.acos(math.sqrt(ratio))
                print(f"test0418: scissors theta_rad={theta_rad}")
                oy = math.degrees(theta_rad)
                oy_rad = math.radians(oy)
                oz_rad = math.atan(math.sin(oy_rad) )
                oz = math.degrees(oz_rad)
                extension_mm = 27.0
                back_x = -extension_mm * math.sin(oy_rad)
                back_y = (-extension_mm / math.sqrt(2))* math.cos(oy_rad)
                back_z = (extension_mm / math.sqrt(2))* math.cos(oy_rad)
                self.right_arm_all_degree_move(135.0, oy, oz-180.0, world_x  , world_y  , world_z + 50) # 移動到指定位置
                self.right_arm_all_degree_move(135.0, oy, oz-180.0, world_x + back_x , world_y + back_y , world_z + back_z -18) # 移動到指定位置
                self.degree_gripper_control("right", 225) # 設定右手
                self.right_arm_all_degree_move(135.0, oy, oz-180.0, world_x  , world_y  , world_z + 50)
                self.arm_pos_move_horizontal("right", world_x  , world_y  , world_z + 50)
                self.right_arm_initial_position() # 右手回到初始位置
                world_x = world_x + back_x
                world_y = world_y + back_y
                world_z = world_z - 18 + back_z
            self.arm_have_object[hand] = obj

        elif obj == "remote_control":
            if hand == "right":
                request_pub = rospy.Publisher("/llm_degree/request", RosString, queue_size=1)
                rospy.sleep(0.05)  # 可選，等連線
                request_pub.publish(RosString(data="go"))

                try:
                    angle_msg = rospy.wait_for_message("/llm_degree/angle", Float32, timeout=10.0)
                    angle_value = float(angle_msg.data)
                except Exception as error:
                    rospy.logerr(f"[{self.action_type}] 取得遙控器角度失敗: {error}，改用預設 45 度")
                    angle_value = 45.0

                rospy.loginfo(f"[{self.action_type}] 遙控器角度={angle_value:.2f} 度")

                oy = angle_value
                oy_rad = math.radians(oy)
                oz_rad = math.atan(math.sin(oy_rad) )
                oz = math.degrees(oz_rad)
                extension_mm = 27.0
                back_x = -extension_mm * math.sin(oy_rad)
                back_y = (-extension_mm / math.sqrt(2))* math.cos(oy_rad)
                back_z = (extension_mm / math.sqrt(2))* math.cos(oy_rad)
                self.right_arm_all_degree_move(135.0, oy, oz-180.0, world_x  , world_y  , world_z + 50) # 移動到指定位置
                self.right_arm_all_degree_move(135.0, oy, oz-180.0, world_x + back_x , world_y + back_y , world_z + back_z -35) # 移動到指定位置
                self.degree_gripper_control("right", 180) # 設定右手
                self.right_arm_all_degree_move(135.0, oy, oz-180.0, world_x  , world_y  , world_z + 50)
                self.arm_pos_move_horizontal("right", world_x  , world_y  , world_z + 100)
                self.right_arm_initial_position() # 右手回到初始位置
                world_x = world_x + back_x
                world_y = world_y + back_y
                world_z = world_z - 35 + back_z
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