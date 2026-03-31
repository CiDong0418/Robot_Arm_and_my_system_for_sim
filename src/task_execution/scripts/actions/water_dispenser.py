import json
import threading

import rospy
from std_msgs.msg import String
import time
from .base_action import BaseAction


class waterDispenserAction(BaseAction):
    """WATER_DISPENSER 動作骨架：先拿 ArUco(id=2) 座標，再留給後續水源動作流程。"""

    def execute(self) -> bool:
        hand = self._resolve_hand_name()
        location = self._resolve_location_id()

        if hand != "right":
            rospy.logerr(f"[{self.action_type}] WATER_DISPENSER 只能使用 right 手，目前 hand={hand}")
            return False
            
        # 確認location是否正確
        if self.now_location_id["now"] != location:
            rospy.logerr(f"[{self.action_type}] 目前位置 ID 為 {self.now_location_id['now']}，與 PICK 指定的 {location} 不符")
            ok = self.move_base_and_wait(*self.location_xyoz_m.get(location, (0.0, 0.0, 0.0)))
            if not ok:
                rospy.logerr(f"[{self.action_type}] 移動到位置 {location} 失敗")
                return False

        rospy.loginfo(f"[{self.action_type}] 開始執行 WATER_DISPENSER @ location={location}, hand={hand}")
        # self.right_arm_all_degree_move(0.0, 140.0, 0.0, 340.0, -130.0, -170.0)
        marker = self._request_aruco_marker_once(target="head", marker_id=2)
        if marker is None:
            rospy.logerr(f"[{self.action_type}] 取得 ArUco id=2 失敗，停止 WATER_DISPENSER")
            return False
        # self.right_arm_all_degree_move(0.0, 140.0, 0.0, 420.0, -130.0, -130.0)
        xyz_mm = marker["xyz_mm"]
        x_mm = float(xyz_mm["x"])
        y_mm = float(xyz_mm["y"])
        z_mm = float(xyz_mm["z"])
        rospy.loginfo(
            f"[{self.action_type}] ArUco id=2 座標(相機座標系): "
            f"x={x_mm:.2f}, y={y_mm:.2f}, z={z_mm:.2f} mm"
        )

        world_x, world_y, world_z = self._to_world_xyz([x_mm, y_mm, z_mm], camera_id=0)
        ox = 0.0
        oy = 180-35.0
        oz = -90.0


        self.right_arm_all_degree_move(ox, oy, oz, world_x - 120, world_y -25, world_z + 65.25)
        self.degree_gripper_control("right", 180)
        self.right_arm_all_degree_move(ox, oy, oz, world_x - 86.92, world_y -29.85, world_z + 65.25)
        # cup
        self.left_arm_all_degree_move(-180.0, 40.0, 0.0, world_x - 92.85, world_y -0.37, world_z - 12.65)
        self.left_arm_all_degree_move(-180.0, 40.0, 0.0, world_x - 52.85, world_y -0.3669, world_z - 12.65)

        self.degree_gripper_control("right", 210)
        time.sleep(3.0)
        self.degree_gripper_control("right", 180)
        # cup
        self.left_arm_all_degree_move(-180.0, 40.0, 0.0, world_x - 92.85, world_y -0.37, world_z - 12.65)
        self.left_arm_initial_position() # 左手回到初始位置
        
        self.right_arm_all_degree_move(ox, oy, oz, world_x - 120, world_y -25, world_z + 65.25)
        self.open_gripper("right")
        self.both_arms_initial_position()



        

        rospy.loginfo(f"[{self.action_type}] WATER_DISPENSER 骨架流程完成")
        return True

    def _request_aruco_marker_once(self, target: str = "head", marker_id: int = 2):
        """
        發一次觸發，再等一次結果，回傳指定 marker_id 的資料。

        回傳格式（成功）:
            {
              "id": 1,
              "xyz_mm": {"x": ..., "y": ..., "z": ...},
              "pixel": {...}
            }
        失敗回傳 None。
        """
        target_topic = "/aruco_detection/target"
        result_topic = "/aruco_detection/result"
        status_topic = "/aruco_detection/status"
        timeout_sec = float(rospy.get_param("/task_execution/aruco_timeout_sec", 5.0))

        state = {
            "result": None,
            "status": None,
        }
        done_event = threading.Event()

        def _cb_result(msg: String):
            try:
                payload = json.loads(msg.data)
            except Exception as error:
                rospy.logwarn(f"[{self.action_type}] aruco result JSON parse 失敗: {error}")
                return

            if not isinstance(payload, dict):
                return

            markers = payload.get("markers", [])
            if not isinstance(markers, list):
                return

            for marker in markers:
                try:
                    if int(marker.get("id")) == int(marker_id):
                        state["result"] = marker
                        done_event.set()
                        return
                except Exception:
                    continue

        def _cb_status(msg: String):
            state["status"] = msg.data.strip()

        sub_result = rospy.Subscriber(result_topic, String, _cb_result, queue_size=1)
        sub_status = rospy.Subscriber(status_topic, String, _cb_status, queue_size=1)
        pub_target = rospy.Publisher(target_topic, String, queue_size=1)

        try:
            rospy.sleep(0.15)
            pub_target.publish(String(data=str(target).strip().lower()))

            if not done_event.wait(timeout=timeout_sec):
                rospy.logerr(
                    f"[{self.action_type}] 等待 ArUco id={marker_id} 逾時，"
                    f"status={state['status']}"
                )
                return None

            return state["result"]
        finally:
            sub_result.unregister()
            sub_status.unregister()