#!/usr/bin/env python3
import threading
import rospy
from std_msgs.msg import String, Float32
from geometry_msgs.msg import PointStamped

from image.srv import GetObjectXYZ, GetObjectXYZResponse


class HeadXYZServiceServer:
    def __init__(self):
        rospy.init_node("head_xyz_service_server", anonymous=False)

        self._default_timeout_sec = float(rospy.get_param("~default_timeout_sec", 8.0))
        self._target_topic = rospy.get_param("~target_topic", "/head_detection/target")
        self._xyz_topic = rospy.get_param("~xyz_topic", "/head_detection/xyz")
        self._radius_topic = rospy.get_param("~radius_topic", "/head_detection/radius")
        self._status_topic = rospy.get_param("~status_topic", "/head_detection/status")

        self._request_lock = threading.Lock()
        self._state_lock = threading.Lock()
        self._result_event = threading.Event()

        self._waiting = False
        self._last_status = None
        self._last_xyz = None
        self._last_radius = 0.0

        self._target_pub = rospy.Publisher(self._target_topic, String, queue_size=1)
        rospy.Subscriber(self._xyz_topic, PointStamped, self._on_xyz, queue_size=1)
        rospy.Subscriber(self._radius_topic, Float32, self._on_radius, queue_size=1)
        rospy.Subscriber(self._status_topic, String, self._on_status, queue_size=1)

        self._service = rospy.Service("/head_detection/get_object_xyz", GetObjectXYZ, self._handle_get_object_xyz)

        rospy.loginfo("[head_xyz_service] Ready. Service: /head_detection/get_object_xyz")

    def _on_xyz(self, msg: PointStamped):
        with self._state_lock:
            if not self._waiting:
                return
            self._last_xyz = (float(msg.point.x), float(msg.point.y), float(msg.point.z), msg.header.frame_id)

    def _on_radius(self, msg: Float32):
        with self._state_lock:
            if not self._waiting:
                return
            self._last_radius = float(msg.data)

    def _on_status(self, msg: String):
        with self._state_lock:
            if not self._waiting:
                return
            self._last_status = msg.data.strip()
            self._result_event.set()

    def _handle_get_object_xyz(self, req):
        target_name = req.target_name.strip()
        timeout_sec = float(req.timeout_sec) if req.timeout_sec > 0.0 else self._default_timeout_sec

        if not target_name:
            return GetObjectXYZResponse(
                success=False,
                message="target_name is empty",
                x=0.0,
                y=0.0,
                z=0.0,
                radius=0.0,
                frame_id="",
            )

        with self._request_lock:
            with self._state_lock:
                self._waiting = True
                self._last_status = None
                self._last_xyz = None
                self._last_radius = 0.0
                self._result_event.clear()

            self._target_pub.publish(String(data=target_name))
            received = self._result_event.wait(timeout=timeout_sec)

            with self._state_lock:
                self._waiting = False
                status_text = self._last_status or "FAIL | no status"
                xyz = self._last_xyz
                radius = self._last_radius

            if not received:
                return GetObjectXYZResponse(
                    success=False,
                    message=f"timeout after {timeout_sec:.1f}s waiting detection result",
                    x=0.0,
                    y=0.0,
                    z=0.0,
                    radius=0.0,
                    frame_id="",
                )

            if not status_text.startswith("OK"):
                return GetObjectXYZResponse(
                    success=False,
                    message=status_text,
                    x=0.0,
                    y=0.0,
                    z=0.0,
                    radius=0.0,
                    frame_id="",
                )

            if xyz is None:
                return GetObjectXYZResponse(
                    success=False,
                    message="status OK but xyz not received",
                    x=0.0,
                    y=0.0,
                    z=0.0,
                    radius=0.0,
                    frame_id="",
                )

            x, y, z, frame_id = xyz
            return GetObjectXYZResponse(
                success=True,
                message=status_text,
                x=x,
                y=y,
                z=z,
                radius=radius,
                frame_id=frame_id,
            )


if __name__ == "__main__":
    try:
        HeadXYZServiceServer()
        rospy.spin()
    except rospy.ROSInterruptException:
        pass
