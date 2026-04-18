#!/usr/bin/env python3
import json
import os
import random

import rospy
from std_msgs.msg import String


def strip_jsonc_comments(text):
    # Remove // comments while preserving content inside JSON strings.
    out = []
    in_string = False
    escape = False
    i = 0

    while i < len(text):
        ch = text[i]

        if escape:
            out.append(ch)
            escape = False
            i += 1
            continue

        if ch == "\\":
            out.append(ch)
            if in_string:
                escape = True
            i += 1
            continue

        if ch == '"':
            in_string = not in_string
            out.append(ch)
            i += 1
            continue

        if not in_string and ch == "/" and i + 1 < len(text) and text[i + 1] == "/":
            # Skip until end of line.
            while i < len(text) and text[i] != "\n":
                i += 1
            continue

        out.append(ch)
        i += 1

    return "".join(out)


def load_eval_tasks(json_path):
    with open(json_path, "r", encoding="utf-8") as f:
        raw = f.read()

    data = json.loads(strip_jsonc_comments(raw))

    tasks = data.get("tasks", [])
    grouped = {"B": [], "I": [], "A": []}

    for task in tasks:
        task_id = str(task.get("id", "")).upper()
        if not task_id:
            continue
        prefix = task_id[0]
        if prefix in grouped:
            grouped[prefix].append(task)

    return grouped


def parse_counts(user_input):
    parts = user_input.strip().split()
    if len(parts) != 3:
        raise ValueError("Please input exactly 3 integers: B I A")

    b_count, i_count, a_count = [int(x) for x in parts]
    if b_count < 0 or i_count < 0 or a_count < 0:
        raise ValueError("Counts must be non-negative integers")

    return b_count, i_count, a_count


def wait_for_subscriber(pub, timeout_sec):
    start = rospy.Time.now()
    timeout = rospy.Duration(timeout_sec)

    while not rospy.is_shutdown():
        if pub.get_num_connections() > 0:
            return True
        if rospy.Time.now() - start > timeout:
            return False
        rospy.sleep(0.1)

    return False


def build_batch(grouped_tasks, b_count, i_count, a_count):
    if b_count > len(grouped_tasks["B"]):
        raise ValueError(
            "Requested B tasks exceeds available count: "
            f"requested {b_count}, available {len(grouped_tasks['B'])}"
        )
    if i_count > len(grouped_tasks["I"]):
        raise ValueError(
            "Requested I tasks exceeds available count: "
            f"requested {i_count}, available {len(grouped_tasks['I'])}"
        )
    if a_count > len(grouped_tasks["A"]):
        raise ValueError(
            "Requested A tasks exceeds available count: "
            f"requested {a_count}, available {len(grouped_tasks['A'])}"
        )

    selected = []
    selected.extend(random.sample(grouped_tasks["B"], b_count))
    selected.extend(random.sample(grouped_tasks["I"], i_count))
    selected.extend(random.sample(grouped_tasks["A"], a_count))
    random.shuffle(selected)
    return selected


def main():
    rospy.init_node("auto_input_node", anonymous=True)
    pub = rospy.Publisher("/user_command", String, queue_size=50)

    default_json_path = os.path.normpath(
        os.path.join(os.path.dirname(__file__), "..", "data", "eval_tasks.json")
    )
    json_path = rospy.get_param("~eval_tasks_path", default_json_path)
    publish_interval = float(rospy.get_param("~publish_interval", 1.0))
    wait_sub_timeout = float(rospy.get_param("~wait_subscriber_timeout", 5.0))

    if publish_interval < 0:
        rospy.logwarn("publish_interval < 0, fallback to 1.0")
        publish_interval = 1.0

    try:
        grouped_tasks = load_eval_tasks(json_path)
    except Exception as exc:
        rospy.logerr(f"Failed to load tasks from {json_path}: {exc}")
        return

    rospy.loginfo("=== Auto Task Input Node Started ===")
    rospy.loginfo(f"Task source: {json_path}")
    rospy.loginfo(
        "Available counts: B=%d, I=%d, A=%d",
        len(grouped_tasks["B"]),
        len(grouped_tasks["I"]),
        len(grouped_tasks["A"]),
    )

    if not wait_for_subscriber(pub, wait_sub_timeout):
        rospy.logwarn(
            "No /user_command subscriber within %.1f sec. Continue anyway.",
            wait_sub_timeout,
        )

    while not rospy.is_shutdown():
        try:
            raw = input("Input counts as 'B I A' (e.g., 3 5 4), or q to exit: ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if raw.lower() in {"q", "quit", "exit"}:
            break

        try:
            b_count, i_count, a_count = parse_counts(raw)
            total = b_count + i_count + a_count
            if total == 0:
                rospy.logwarn("Total selected tasks is 0. Please input again.")
                continue

            batch = build_batch(grouped_tasks, b_count, i_count, a_count)
        except Exception as exc:
            rospy.logwarn(str(exc))
            continue

        rospy.loginfo("Publishing %d tasks with interval %.2f sec", len(batch), publish_interval)

        for idx, task in enumerate(batch, start=1):
            if rospy.is_shutdown():
                break

            task_id = task.get("id", "UNKNOWN")
            task_text = task.get("text", "")

            rospy.loginfo("[%d/%d] Send %s: %s", idx, len(batch), task_id, task_text)
            pub.publish(task_text)

            if idx < len(batch):
                rospy.sleep(publish_interval)


if __name__ == "__main__":
    try:
        main()
    except rospy.ROSInterruptException:
        pass