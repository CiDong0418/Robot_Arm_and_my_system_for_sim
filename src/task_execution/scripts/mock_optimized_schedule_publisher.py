#!/usr/bin/env python3
import json
import rospy
from std_msgs.msg import String


TEST_PAYLOAD = [
    {
        "timestamp": "2026-03-21 08:05:15",
        "parent_task_id": 1,
        "parent_task_name": "Move Cola to Living Room Table 2",
        "subtasks": [
            {
                "step_id": 1,
                "action_type": "PICK",
                "target_object": "cup",
                "location_id": 1,
                "hand_used": "Left_Arm",
                "estimated_duration": 5,
                "dependencies": [],
                "description": "Pick up the bottle of tea from Living Room Table 1 (location 1).",
                "parent_id": 1,
                "global_id": "1_1"
            },
            # {
            #     "step_id": 2,
            #     "action_type": "PLACE",
            #     "target_object": "cola",
            #     "location_id": 2,
            #     "hand_used": "Right_Arm",
            #     "estimated_duration": 5,
            #     "dependencies": [
            #         "1_1"
            #     ],
            #     "description": "Place the cola on Living Room Table 2 (location 2).",
            #     "parent_id": 1,
            #     "global_id": "1_2"
            # },
            {
                "step_id": 2,
                "action_type": "PICK",
                "target_object": "water",
                "location_id": 1,
                "hand_used": "Right_Arm",
                "estimated_duration": 5,
                "dependencies": [],
                "description": "Pick up the cola from Living Room Table 1 (location 1).",
                "parent_id": 1,
                "global_id": "1_2"
            },
            {
                "step_id": 3,
                "action_type": "POUR",
                "target_object": "water -> cup",
                "location_id": 1,
                "hand_used": "Right_Arm",
                "estimated_duration": 8,
                "dependencies": [
                  "1_1",
                  "1_2"
                ],
                "description": "Pour water into the cup at Kitchen Table 1 (location 1). Requires holding both water and cup first.",
                "parent_id": 1,
                "global_id": "1_3"
            }
        ]
    }
]


def _build_schedule_tasks(payload):
    if not isinstance(payload, list):
        raise ValueError("payload 必須是 list")

    schedule_tasks = []
    for item in payload:
        if not isinstance(item, dict):
            continue

        subtasks = item.get("subtasks")
        if isinstance(subtasks, list):
            for subtask in subtasks:
                if isinstance(subtask, dict):
                    schedule_tasks.append(subtask)
        elif "action_type" in item:
            schedule_tasks.append(item)

    return schedule_tasks


def main():
    rospy.init_node("mock_optimized_schedule_publisher", anonymous=False)

    topic_name = rospy.get_param("~topic", "/optimized_schedule")
    repeat = int(rospy.get_param("~repeat", 1))
    interval_sec = float(rospy.get_param("~interval_sec", 0.5))
    wait_subscriber_sec = float(rospy.get_param("~wait_subscriber_sec", 2.0))

    pub = rospy.Publisher(topic_name, String, queue_size=10)

    tasks = _build_schedule_tasks(TEST_PAYLOAD)
    if not tasks:
        rospy.logerr("[MockSchedule] 沒有可發布的任務，請檢查 TEST_PAYLOAD")
        return

    output_json = json.dumps(tasks, ensure_ascii=False)

    rospy.sleep(0.2)
    start = rospy.Time.now().to_sec()
    while pub.get_num_connections() == 0 and not rospy.is_shutdown():
        if rospy.Time.now().to_sec() - start > wait_subscriber_sec:
            break
        rospy.sleep(0.1)

    for idx in range(max(1, repeat)):
        if rospy.is_shutdown():
            return
        pub.publish(String(data=output_json))
        rospy.loginfo(
            f"[MockSchedule] Published to {topic_name} ({idx + 1}/{max(1, repeat)}), task_count={len(tasks)}"
        )
        rospy.sleep(interval_sec)

    rospy.loginfo("[MockSchedule] Done. 你可以直接改 TEST_PAYLOAD 測不同物件/任務。")


if __name__ == "__main__":
    try:
        main()
    except rospy.ROSInterruptException:
        pass
