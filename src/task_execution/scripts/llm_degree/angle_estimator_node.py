#!/usr/bin/env python3
import base64
import json
import os
import threading
import time

import cv2
import numpy as np
import rospy
from cv_bridge import CvBridge
from dotenv import load_dotenv
from openai import OpenAI
from sensor_msgs.msg import Image, CompressedImage
from std_msgs.msg import Float32, String


SYSTEM_PROMPT = """
You are a precise visual angle estimator.
Return only JSON.
"""

USER_PROMPT = """
Given the image, find the remote control.
Estimate the angle between the remote control's long side (long axis) and the horizontal axis of the image.
Angle convention:
- 0 deg = perfectly horizontal (long axis left-to-right).
- Positive angles rotate counterclockwise.
- Range:  0 to +90.
Use the reference images provided. Choose the single most likely angle among the reference set
based on visual similarity. Do NOT invent a new angle that is not in the reference set.
If the remote is not visible, return {"found": false}.
Otherwise return:
{"found": true, "angle_deg": <number>, "confidence": <0-1>}
Be concise and do not add any extra text.
"""


class AngleEstimatorNode:
    def __init__(self):
        rospy.init_node("angle_estimator_node")

        self.image_topic = rospy.get_param("~image_topic", "/head_camera/color/image_raw")
        self.use_compressed = rospy.get_param("~use_compressed", False)
        self.display = rospy.get_param("~display", False)
        self.model = rospy.get_param("~model", "gpt-4o")
        self.request_topic = rospy.get_param("~request_topic", "/llm_degree/request")
        self.reference_dir = rospy.get_param(
            "~reference_dir",
            os.path.abspath(os.path.join(os.path.dirname(__file__), ".")),
        )
        self.reference_angles = rospy.get_param("~reference_angles", "0,30,45,70,90")

        env_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.env"))
        load_dotenv(dotenv_path=env_path)
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY not found in .env")

        self.client = OpenAI(api_key=api_key)
        self.bridge = CvBridge()
        self.reference_images = self._load_reference_images()
        self.latest_frame = None
        self.frame_lock = threading.Lock()
        self.inflight_lock = threading.Lock()
        self.is_inflight = False

        self.angle_pub = rospy.Publisher("/llm_degree/angle", Float32, queue_size=10)
        self.result_pub = rospy.Publisher("/llm_degree/result", String, queue_size=10)
        self.status_pub = rospy.Publisher("/llm_degree/status", String, queue_size=10)

        if self.use_compressed:
            self.sub = rospy.Subscriber(self.image_topic, CompressedImage, self._cb_compressed, queue_size=1)
        else:
            self.sub = rospy.Subscriber(self.image_topic, Image, self._cb_raw, queue_size=1)

        self.request_sub = rospy.Subscriber(self.request_topic, String, self._on_request, queue_size=1)

        rospy.loginfo("[AngleEstimator] Ready. topic=%s compressed=%s model=%s", self.image_topic, self.use_compressed, self.model)
        rospy.loginfo("[AngleEstimator] Request topic: %s", self.request_topic)
        if self.reference_images:
            rospy.loginfo("[AngleEstimator] Loaded %d reference images from %s", len(self.reference_images), self.reference_dir)
        else:
            rospy.logwarn("[AngleEstimator] No reference images loaded. Using single-image estimation.")

    def _cb_raw(self, msg):
        try:
            frame = self.bridge.imgmsg_to_cv2(msg, desired_encoding="bgr8")
        except Exception as error:
            rospy.logwarn("[AngleEstimator] imgmsg_to_cv2 failed: %s", error)
            return
        with self.frame_lock:
            self.latest_frame = frame

    def _cb_compressed(self, msg):
        try:
            np_arr = np.frombuffer(msg.data, np.uint8)
            frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        except Exception as error:
            rospy.logwarn("[AngleEstimator] decode compressed failed: %s", error)
            return
        if frame is None:
            return
        with self.frame_lock:
            self.latest_frame = frame

    def _on_request(self, msg):
        with self.inflight_lock:
            if self.is_inflight:
                self.status_pub.publish(String(data="BUSY"))
                return
            self.is_inflight = True

        with self.frame_lock:
            frame = None if self.latest_frame is None else self.latest_frame.copy()

        if frame is None:
            self.status_pub.publish(String(data="NO_FRAME"))
            with self.inflight_lock:
                self.is_inflight = False
            return

        threading.Thread(target=self._process_frame, args=(frame,), daemon=True).start()

    def _process_frame(self, frame):
        start_ts = time.time()
        try:
            image_b64 = self._encode_image(frame)
            if not image_b64:
                return

            result = self._call_llm(image_b64)
            if not result:
                return

            if not result.get("found"):
                self.status_pub.publish(String(data="NOT_FOUND"))
                self.result_pub.publish(String(data=json.dumps(result)))
                return

            angle = result.get("angle_deg")
            if angle is None:
                return

            try:
                angle_value = float(angle)
            except (TypeError, ValueError):
                return

            self.angle_pub.publish(Float32(data=angle_value))
            self.status_pub.publish(String(data=f"OK angle={angle_value:.2f}"))
            self.result_pub.publish(String(data=json.dumps(result)))
            rospy.loginfo_throttle(1.0, "[AngleEstimator] angle=%.2f deg", angle_value)

            if self.display:
                cv2.putText(frame, f"angle: {angle_value:.2f}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
                cv2.imshow("angle_llm", frame)
                cv2.waitKey(1)

            elapsed = time.time() - start_ts
            rospy.loginfo_throttle(1.0, "[AngleEstimator] inference_time=%.2f sec", elapsed)
        finally:
            with self.inflight_lock:
                self.is_inflight = False

    def _encode_image(self, frame):
        success, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
        if not success:
            return None
        return base64.b64encode(buf.tobytes()).decode("ascii")

    def _load_reference_images(self):
        reference_images = []
        angles = []
        for token in str(self.reference_angles).split(","):
            token = token.strip()
            if not token:
                continue
            try:
                angles.append(int(token))
            except ValueError:
                continue

        for angle in angles:
            filename = f"{angle}.png"
            path = os.path.join(self.reference_dir, filename)
            if not os.path.isfile(path):
                rospy.logwarn("[AngleEstimator] Reference image missing: %s", path)
                continue
            image = cv2.imread(path)
            if image is None:
                rospy.logwarn("[AngleEstimator] Failed to read reference image: %s", path)
                continue
            encoded = self._encode_image(image)
            if not encoded:
                rospy.logwarn("[AngleEstimator] Failed to encode reference image: %s", path)
                continue
            reference_images.append((angle, encoded))
        return reference_images

    def _call_llm(self, image_b64):
        content = [{"type": "text", "text": USER_PROMPT}]
        if self.reference_images:
            content.append({"type": "text", "text": "Reference images with known angles:"})
            for angle, ref_b64 in self.reference_images:
                content.append({"type": "text", "text": f"Reference angle: {angle} deg"})
                content.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{ref_b64}"}})
            content.append({"type": "text", "text": "Query image:"})
        content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}})

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": content,
                    },
                ],
                temperature=0.1,
                response_format={"type": "json_object"},
            )
        except Exception as error:
            rospy.logwarn("[AngleEstimator] LLM request failed: %s", error)
            self.status_pub.publish(String(data="ERROR"))
            return None

        content = response.choices[0].message.content
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            rospy.logwarn("[AngleEstimator] Invalid JSON: %s", content)
            self.status_pub.publish(String(data="BAD_JSON"))
            return None
        return data


if __name__ == "__main__":
    try:
        AngleEstimatorNode()
        rospy.spin()
    except rospy.ROSInterruptException:
        pass
