import rospy
from image.srv import GetObjectXYZ, GetObjectXYZRequest

from .base_action import BaseAction


class PickAction(BaseAction):
    """PICK 動作執行器：負責取得目標物座標並銜接後續夾取流程。"""

    def _resolve_object_name(self):
        # 這一個func的功能是:
        # 兼容不同上游欄位命名，優先順序由前到後
        return (
            self.task_data.get("object")
            or self.task_data.get("target_object")
            or self.task_data.get("item_name")
        )

    def _resolve_hand_name(self):
        # 這一個func的功能是:
        # 兼容 hand / hand_used 欄位
        hand_name = self.task_data.get("hand") or self.task_data.get("hand_used")
        if not isinstance(hand_name, str):
            return hand_name

        # 將排程層名稱映射為底層控制常用名稱
        hand_key = hand_name.strip().lower()
        hand_map = {
            "left_arm": "left",
            "right_arm": "right",
            "left": "left",
            "right": "right",
        }
        return hand_map.get(hand_key, hand_name)

    def _request_object_xyz(self, object_name: str):
        # 這一個func的功能是:
        # object_name 是要請視覺端去找的目標物名稱
        # 得到物體位置 XYZ 和半徑 R（mm）以及座標系 frame_id（通常是相機座標系）
        # 從 ROS 參數讀取 service 位置與等待逾時秒數
        service_name = rospy.get_param("/task_execution/object_xyz_service_name", "/head_detection/get_object_xyz")
        timeout_sec = float(rospy.get_param("/task_execution/object_xyz_timeout_sec", 8.0))

        # 先等 service 就緒，避免直接呼叫時阻塞/拋例外
        try:
            rospy.wait_for_service(service_name, timeout=timeout_sec)
        except rospy.ROSException:
            rospy.logerr(f"[{self.action_type}] 等待 service {service_name} 逾時")
            return None

        # 發送目標物名稱，請求視覺端回傳 XYZ
        try:
            service_proxy = rospy.ServiceProxy(service_name, GetObjectXYZ)
            request = GetObjectXYZRequest(target_name=object_name, timeout_sec=timeout_sec)
            response = service_proxy(request)
        except rospy.ServiceException as error:
            rospy.logerr(f"[{self.action_type}] 呼叫 {service_name} 失敗: {error}")
            return None

        # service 回傳失敗時直接回傳 None，交由 execute() 統一處理
        if not response.success:
            rospy.logerr(f"[{self.action_type}] 物件 '{object_name}' 座標取得失敗: {response.message}")
            return None

        return response # 格式為 GetObjectXYZResponse，包含 success, message, x, y, z, radius, frame_id 等欄位
        # return GetObjectXYZResponse(
        #         success=False,
        #         message="target_name is empty",
        #         x=0.0,
        #         y=0.0,
        #         z=0.0,
        #         radius=0.0,
        #         frame_id="",
        #     )

    def _to_world_xyz(self, camera_xyz_mm, camera_id=0):
        # 若關閉座標轉換，直接使用相機座標
        use_camera_transfer = bool(rospy.get_param("/task_execution/use_camera_transfer", True))
        if not use_camera_transfer:
            return camera_xyz_mm

        # 使用你原本的 camera_transfer 轉成機器人世界座標
        try:
            world_xyz = self.camera_transfer.list_transform_points(camera_id, list(camera_xyz_mm))
            if world_xyz and len(world_xyz) >= 3:
                return [float(world_xyz[0]), float(world_xyz[1]), float(world_xyz[2])]
        except Exception as error:
            # 轉換失敗時不中斷整個流程，退回原始相機座標
            rospy.logwarn(f"[{self.action_type}] camera_transfer 轉換失敗，改用原始座標: {error}")

        return camera_xyz_mm
        # 格式為 [x_mm, y_mm, z_mm] 的 list，單位為毫米

    def execute(self) -> bool:
        # 1) 解析任務參數
        obj = self._resolve_object_name()
        hand = self._resolve_hand_name()
        location = self.task_data.get("location_id")
        # camera_id = self.task_data.get("camera_id", 0)  # 預設使用 camera_id 0

        # 2) 基本防呆：沒有目標物就無法執行 PICK
        if not obj:
            rospy.logerr(f"[{self.action_type}] 缺少物件名稱，請確認 task 內有 object/target_object")
            return False

        rospy.loginfo(f"[{self.action_type}] 開始執行 PICK: 使用 {hand} 手抓取 {location} 的 {obj}")

        # 3) 向視覺 service 取得物件表面座標（camera frame）
        result = self._request_object_xyz(obj)
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

        rospy.sleep(2.0)  # 模擬動作執行時間
        rospy.loginfo(f"[{self.action_type}] PICK 執行完畢！")
        return True