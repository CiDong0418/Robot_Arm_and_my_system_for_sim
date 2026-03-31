import json
import threading

import rospy
from std_msgs.msg import String

from .base_action import BaseAction


class openDrawerAction(BaseAction):
    """OPEN_DRAWER 動作骨架：先拿 ArUco(id=1) 座標，再留給後續抽屜動作流程。"""

    def execute(self) -> bool:
        hand = self._resolve_hand_name()
        location = self._resolve_location_id()

        if hand != "left":
            rospy.logerr(f"[{self.action_type}] OPEN_DRAWER 只能使用 left 手，目前 hand={hand}")
            return False
            
        # 確認location是否正確
        if self.now_location_id["now"] != location:
            rospy.logerr(f"[{self.action_type}] 目前位置 ID 為 {self.now_location_id['now']}，與 PICK 指定的 {location} 不符")
            ok = self.move_base_and_wait(*self.location_xyoz_m.get(location, (0.0, 0.0, 0.0)))
            if not ok:
                rospy.logerr(f"[{self.action_type}] 移動到位置 {location} 失敗")
                return False

        rospy.loginfo(f"[{self.action_type}] 開始執行 OPEN_DRAWER @ location={location}, hand={hand}")
        self.right_arm_all_degree_move(0.0, 140.0, 0.0, 340.0, -130.0, -170.0)
        marker = self._request_aruco_marker_once(target="head", marker_id=1)
        if marker is None:
            rospy.logerr(f"[{self.action_type}] 取得 ArUco id=1 失敗，停止 OPEN_DRAWER")
            return False
        self.right_arm_all_degree_move(0.0, 140.0, 0.0, 420.0, -130.0, -130.0)
        xyz_mm = marker["xyz_mm"]
        x_mm = float(xyz_mm["x"])
        y_mm = float(xyz_mm["y"])
        z_mm = float(xyz_mm["z"])
        rospy.loginfo(
            f"[{self.action_type}] ArUco id=1 座標(相機座標系): "
            f"x={x_mm:.2f}, y={y_mm:.2f}, z={z_mm:.2f} mm"
        )

        world_x, world_y, world_z = self._to_world_xyz([x_mm, y_mm, z_mm], camera_id=0)
        ox = -180.0
        oy = 22.5
        oz = 0.0
        world_y = world_y - 45

        self.degree_gripper_control("left", 140)
        self.left_arm_all_degree_move(ox, oy, oz, world_x - 95, world_y + 120, world_z - 35)
        self.right_arm_all_degree_move(0.0, (180.0 - 22.5), 0.0, world_x - 110, world_y + 55, world_z + 160)
        self.left_arm_all_degree_move(ox, oy, oz, world_x - 60, world_y + 120, world_z - 35)
        self.left_arm_all_degree_move(ox, oy, oz, world_x - 60, world_y + 90, world_z - 35)
        self.degree_gripper_control("left", 170)
        self.left_arm_all_degree_move(ox, oy, oz, world_x - 140, world_y + 90, world_z - 35)
        self.left_arm_all_degree_move(ox, oy, oz, world_x - 220, world_y + 90, world_z - 35)
        self.open_gripper("right")
        self.left_arm_all_degree_move(ox, oy, oz, world_x - 135, world_y + 90, world_z - 35)
        self.left_arm_all_degree_move(ox, oy, oz, world_x - 50, world_y + 90, world_z - 35)
        self.left_arm_all_degree_move(ox, oy, oz, world_x - 60, world_y + 90, world_z - 35)
        self.degree_gripper_control("left", 140)
        self.left_arm_all_degree_move(ox, oy, oz, world_x - 60, world_y + 120, world_z - 35)
        self.left_arm_all_degree_move(ox, oy, oz, world_x - 95, world_y + 120, world_z - 35)
        self.both_arms_initial_position()
        self.open_gripper("left")
        self.arm_have_object["right"] = None

        rospy.loginfo(f"[{self.action_type}] OPEN_DRAWER 骨架流程完成（動作序列待填）")
        return True

    def _request_aruco_marker_once(self, target: str = "head", marker_id: int = 1):
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