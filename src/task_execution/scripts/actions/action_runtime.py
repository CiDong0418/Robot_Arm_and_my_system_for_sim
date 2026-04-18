import os
import sys
import threading

import rospy


_runtime_lock = threading.Lock()
_runtime_initialized = False
_robot_control = None
_camera_transfer = None


def _ensure_software_root_in_sys_path():
    candidate_roots = [
        os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../")),
        "/home/aiRobots/Software",
    ]

    for root_path in candidate_roots:
        if not os.path.isfile(os.path.join(root_path, "actionCommand.py")):
            continue
        if root_path not in sys.path:
            sys.path.append(root_path)
        return


def get_action_runtime():
    global _runtime_initialized, _robot_control, _camera_transfer

    with _runtime_lock:
        if _runtime_initialized:
            return _robot_control, _camera_transfer

        _ensure_software_root_in_sys_path()

        try:   
            from actionCommand import PostureCommandPublisher
            from camera_transfer import CameraTransfer
        except Exception as error:
            rospy.logerr(f"[ActionRuntime] 載入 actionCommand/camera_transfer 失敗: {error}")
            raise

        try:
            _robot_control = PostureCommandPublisher()
            _camera_transfer = CameraTransfer()
        except Exception as error:
            rospy.logerr(f"[ActionRuntime] 初始化控制介面失敗: {error}")
            raise

        _runtime_initialized = True
        rospy.loginfo("[ActionRuntime] PostureCommandPublisher + CameraTransfer 已就緒")
        return _robot_control, _camera_transfer
