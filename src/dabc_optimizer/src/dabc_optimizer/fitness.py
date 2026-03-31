import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../task_manager/src')))
from task_module.topology_map import TopologicalMap

_topo = TopologicalMap()

# ============================================================
# 固定動作時間表 (秒) — 不依賴 LLM 的 estimated_duration
# 若 LLM 沒給或給的不合理，一律用這裡的數值
# ============================================================
ACTION_DURATION = {
    "PICK":               15,   # 手臂抓取物品
    "PLACE":              5,   # 手臂放下物品
    "POUR":               9,   # 傾倒液體
    "HANDOVER":           12,   # 換手
    "STORE_ON_TRAY":      5,   # 放到胸前托盤
    "RETRIEVE_FROM_TRAY": 13,   # 從托盤取回
    "WAIT":              10,   # 等待 (預設)
}
DEFAULT_ACTION_DURATION = 12    # 未知動作的預設時間
TRAY_SUPPORTED_OBJECTS = {"cup", "cola", "juice", "water", "tea"}

class TaskScheduler:
    def __init__(self, task_lookup):
        """
        :param task_lookup: 字典格式 {id: {duration, hand, deps, action_type, location_id, ...}}
        """
        self.tasks = task_lookup
        self.tray_capacity = 1

    def calculate_makespan(self, sequence):
        """
        計算 Makespan，同時考慮：
        1. 依賴關係 (Dependency)
        2. 手臂容量狀態 (Hand Capacity) - 避免滿手時還去抓東西
        3. 隱性移動成本 (Implicit Travel Cost) - 根據前後任務的 location_id 自動計算移動時間
        """
        _, makespan = self._simulate(sequence, record_actions=False)
        return makespan

    def build_execution_plan(self, sequence):
        return self._simulate(sequence, record_actions=True)

    def _normalize_hand(self, hand):
        if not hand:
            return None
        if isinstance(hand, str):
            key = hand.strip().lower()
            if key in ["left_arm", "left"]:
                return "Left_Arm"
            if key in ["right_arm", "right"]:
                return "Right_Arm"
        return hand

    def _parse_object_name(self, target_object):
        if target_object is None:
            return None
        text = str(target_object).strip().lower()
        if "->" in text:
            left, _ = text.split("->", 1)
            return left.strip()
        return text

    def _extract_pour_source(self, target_object):
        if target_object is None:
            return None
        text = str(target_object).strip().lower()
        if "->" in text:
            left, _ = text.split("->", 1)
            return left.strip()
        return text

    def _action_requires_hand(self, action):
        return action in [
            "PICK",
            "PLACE",
            "POUR",
            "HANDOVER",
            "STORE_ON_TRAY",
            "RETRIEVE_FROM_TRAY",
            "OPEN_DRAWER",
        ]

    def _allowed_hands(self, action, target_object):
        if action == "OPEN_DRAWER":
            return ["Left_Arm"]

        obj_name = self._parse_object_name(target_object)
        if obj_name == "scissors" and action in [
            "PICK",
            "PLACE",
            "STORE_ON_TRAY",
            "RETRIEVE_FROM_TRAY",
            "POUR",
        ]:
            return ["Right_Arm"]

        return ["Left_Arm", "Right_Arm"]

    def _choose_available_hand(self, allowed_hands, hand_holding, resource_clock, min_start):
        candidates = []
        for hand in allowed_hands:
            if hand_holding.get(hand) is None:
                ready_time = max(min_start, resource_clock.get(hand, 0))
                candidates.append((ready_time, hand))
        if not candidates:
            return None
        candidates.sort(key=lambda item: (item[0], item[1]))
        return candidates[0][1]

    def _choose_hand_to_store(self, hand_holding, resource_clock):
        candidates = []
        for hand, obj in hand_holding.items():
            if obj is not None:
                candidates.append((resource_clock.get(hand, 0), hand))
        if not candidates:
            return None
        candidates.sort(key=lambda item: (item[0], item[1]))
        return candidates[-1][1]

    def _simulate(self, sequence, record_actions=False):
        # --- 1. 初始化狀態 ---
        resource_clock = {
            "Left_Arm": 0,
            "Right_Arm": 0,
            "Base": 0,
        }

        hand_holding = {
            "Left_Arm": None,
            "Right_Arm": None,
        }

        tray_contents = []

        current_location_id = 1
        task_finish_times = {}
        planned_tasks = []
        insert_seq = 0

        def schedule_action(task_payload, action_type, hand, location_id, target_object, min_start_time, is_synthetic=False, secondary_hand=None):
            nonlocal current_location_id

            action_duration = ACTION_DURATION.get(
                action_type,
                task_payload.get("estimated_duration", DEFAULT_ACTION_DURATION) if task_payload else DEFAULT_ACTION_DURATION,
            )

            travel_time = _topo.get_travel_time(current_location_id, location_id)
            start_ready = max(min_start_time, resource_clock.get("Base", 0))

            if hand == "Left_Arm":
                start_ready = max(start_ready, resource_clock.get("Left_Arm", 0))
            elif hand == "Right_Arm":
                start_ready = max(start_ready, resource_clock.get("Right_Arm", 0))

            if secondary_hand == "Left_Arm":
                start_ready = max(start_ready, resource_clock.get("Left_Arm", 0))
            elif secondary_hand == "Right_Arm":
                start_ready = max(start_ready, resource_clock.get("Right_Arm", 0))

            start_time = start_ready + travel_time
            end_time = start_time + action_duration

            if hand == "Left_Arm":
                resource_clock["Left_Arm"] = end_time
                resource_clock["Base"] = start_time
            elif hand == "Right_Arm":
                resource_clock["Right_Arm"] = end_time
                resource_clock["Base"] = start_time
            else:
                resource_clock["Base"] = end_time

            if secondary_hand == "Left_Arm":
                resource_clock["Left_Arm"] = max(resource_clock["Left_Arm"], end_time)
            elif secondary_hand == "Right_Arm":
                resource_clock["Right_Arm"] = max(resource_clock["Right_Arm"], end_time)

            current_location_id = location_id

            if record_actions:
                task_data = {}
                if task_payload:
                    task_data.update(task_payload)
                task_data.update({
                    "action_type": action_type,
                    "hand_used": hand,
                    "location_id": location_id,
                    "target_object": target_object,
                    "estimated_duration": action_duration,
                })
                if is_synthetic:
                    task_data.setdefault("description", f"Auto-inserted {action_type} for tray handling.")
                planned_tasks.append(task_data)

            return end_time

        for task_id in sequence:
            if task_id not in self.tasks:
                return planned_tasks, float("inf")

            task = self.tasks[task_id]
            action = task.get("action_type", "PICK")
            task_location_id = task.get("location_id", current_location_id)
            target_object = task.get("target_object")

            # === 檢查 A: 依賴關係 (Dependency Check) ===
            start_time_by_deps = 0
            for dep_id in task.get("dependencies", []):
                if dep_id not in task_finish_times:
                    return planned_tasks, float("inf")
                start_time_by_deps = max(start_time_by_deps, task_finish_times[dep_id])

            normalized_hand = self._normalize_hand(task.get("hand_used"))

            if not self._action_requires_hand(action):
                end_time = schedule_action(task, action, None, task_location_id, target_object, start_time_by_deps)
                task_finish_times[task_id] = end_time
                continue

            allowed_hands = self._allowed_hands(action, target_object)
            if normalized_hand and normalized_hand not in allowed_hands:
                return planned_tasks, float("inf")

            chosen_hand = normalized_hand

            if action == "PICK":
                if chosen_hand is None:
                    chosen_hand = self._choose_available_hand(allowed_hands, hand_holding, resource_clock, start_time_by_deps)

                if chosen_hand is None:
                    # If this pick must use Right_Arm (e.g., scissors), attempt a handover first.
                    if allowed_hands == ["Right_Arm"]:
                        if hand_holding.get("Right_Arm") is not None and hand_holding.get("Left_Arm") is None:
                            insert_seq += 1
                            handover_payload = {
                                "global_id": f"{task_id}_handover_{insert_seq}",
                                "parent_id": task.get("parent_id"),
                                "from_hand": "Right_Arm",
                                "to_hand": "Left_Arm",
                            }
                            obj_name = hand_holding.get("Right_Arm")
                            hand_holding["Right_Arm"] = None
                            hand_holding["Left_Arm"] = obj_name
                            end_time = schedule_action(
                                handover_payload,
                                "HANDOVER",
                                "Right_Arm",
                                task_location_id,
                                obj_name,
                                start_time_by_deps,
                                is_synthetic=True,
                                secondary_hand="Left_Arm",
                            )
                            task_finish_times[handover_payload["global_id"]] = end_time
                            chosen_hand = self._choose_available_hand(allowed_hands, hand_holding, resource_clock, start_time_by_deps)
                            if chosen_hand is None:
                                return planned_tasks, float("inf")
                        else:
                            return planned_tasks, float("inf")

                if chosen_hand is None:
                    if len(tray_contents) >= self.tray_capacity:
                        return planned_tasks, float("inf")

                    hand_to_store = self._choose_hand_to_store(hand_holding, resource_clock)
                    if hand_to_store is None:
                        return planned_tasks, float("inf")

                    stored_obj = hand_holding.get(hand_to_store)
                    if stored_obj and stored_obj not in TRAY_SUPPORTED_OBJECTS:
                        return planned_tasks, float("inf")
                    insert_seq += 1
                    store_task_payload = {
                        "global_id": f"{task_id}_store_{insert_seq}",
                        "parent_id": task.get("parent_id"),
                    }
                    end_time = schedule_action(
                        store_task_payload,
                        "STORE_ON_TRAY",
                        hand_to_store,
                        task_location_id,
                        stored_obj,
                        start_time_by_deps,
                        is_synthetic=True,
                    )
                    tray_contents.append(stored_obj)
                    hand_holding[hand_to_store] = None
                    task_finish_times[store_task_payload["global_id"]] = end_time

                    chosen_hand = self._choose_available_hand(allowed_hands, hand_holding, resource_clock, start_time_by_deps)
                    if chosen_hand is None:
                        return planned_tasks, float("inf")

                if hand_holding.get(chosen_hand) is not None:
                    return planned_tasks, float("inf")
                hand_holding[chosen_hand] = self._parse_object_name(target_object) or "HOLDING_SOMETHING"

            elif action == "PLACE":
                obj_name = self._parse_object_name(target_object)

                if chosen_hand is None:
                    if obj_name:
                        for hand_name, holding_obj in hand_holding.items():
                            if holding_obj == obj_name:
                                chosen_hand = hand_name
                                break

                if chosen_hand is None and obj_name and obj_name in tray_contents:
                    retrieve_hand = self._choose_available_hand(allowed_hands, hand_holding, resource_clock, start_time_by_deps)
                    if retrieve_hand is None:
                        return planned_tasks, float("inf")

                    insert_seq += 1
                    retrieve_payload = {
                        "global_id": f"{task_id}_retrieve_{insert_seq}",
                        "parent_id": task.get("parent_id"),
                    }
                    end_time = schedule_action(
                        retrieve_payload,
                        "RETRIEVE_FROM_TRAY",
                        retrieve_hand,
                        task_location_id,
                        obj_name,
                        start_time_by_deps,
                        is_synthetic=True,
                    )
                    tray_contents.remove(obj_name)
                    hand_holding[retrieve_hand] = obj_name
                    task_finish_times[retrieve_payload["global_id"]] = end_time
                    chosen_hand = retrieve_hand

                if chosen_hand is None or hand_holding.get(chosen_hand) is None:
                    return planned_tasks, float("inf")

                if obj_name and hand_holding.get(chosen_hand) != obj_name:
                    return planned_tasks, float("inf")

                hand_holding[chosen_hand] = None

            elif action == "STORE_ON_TRAY":
                if len(tray_contents) >= self.tray_capacity:
                    return planned_tasks, float("inf")

                obj_name = self._parse_object_name(target_object)
                if obj_name and obj_name not in TRAY_SUPPORTED_OBJECTS:
                    return planned_tasks, float("inf")
                if chosen_hand is None and obj_name:
                    for hand_name, holding_obj in hand_holding.items():
                        if holding_obj == obj_name:
                            chosen_hand = hand_name
                            break

                if chosen_hand is None:
                    chosen_hand = self._choose_hand_to_store(hand_holding, resource_clock)

                if chosen_hand is None or hand_holding.get(chosen_hand) is None:
                    return planned_tasks, float("inf")

                stored_obj = hand_holding.get(chosen_hand)
                tray_contents.append(stored_obj)
                hand_holding[chosen_hand] = None

            elif action == "RETRIEVE_FROM_TRAY":
                obj_name = self._parse_object_name(target_object)
                if obj_name and obj_name not in tray_contents:
                    return planned_tasks, float("inf")

                if chosen_hand is None:
                    chosen_hand = self._choose_available_hand(allowed_hands, hand_holding, resource_clock, start_time_by_deps)

                if chosen_hand is None or hand_holding.get(chosen_hand) is not None:
                    return planned_tasks, float("inf")

                if obj_name:
                    tray_contents.remove(obj_name)
                    hand_holding[chosen_hand] = obj_name
                else:
                    if not tray_contents:
                        return planned_tasks, float("inf")
                    hand_holding[chosen_hand] = tray_contents.pop(0)

            elif action == "POUR":
                source_obj = self._extract_pour_source(target_object)
                if chosen_hand is None and source_obj:
                    for hand_name, holding_obj in hand_holding.items():
                        if holding_obj == source_obj:
                            chosen_hand = hand_name
                            break

                if chosen_hand is None or hand_holding.get(chosen_hand) is None:
                    return planned_tasks, float("inf")

            elif action == "OPEN_DRAWER":
                if chosen_hand is None:
                    chosen_hand = "Left_Arm"

                if chosen_hand != "Left_Arm":
                    return planned_tasks, float("inf")

                if hand_holding.get("Left_Arm") is not None:
                    if len(tray_contents) >= self.tray_capacity:
                        return planned_tasks, float("inf")

                    stored_obj = hand_holding.get("Left_Arm")
                    if stored_obj and stored_obj not in TRAY_SUPPORTED_OBJECTS:
                        return planned_tasks, float("inf")

                    insert_seq += 1
                    store_task_payload = {
                        "global_id": f"{task_id}_store_{insert_seq}",
                        "parent_id": task.get("parent_id"),
                    }
                    end_time = schedule_action(
                        store_task_payload,
                        "STORE_ON_TRAY",
                        "Left_Arm",
                        task_location_id,
                        stored_obj,
                        start_time_by_deps,
                        is_synthetic=True,
                    )
                    tray_contents.append(stored_obj)
                    hand_holding["Left_Arm"] = None
                    task_finish_times[store_task_payload["global_id"]] = end_time

            elif action == "HANDOVER":
                from_hand = self._normalize_hand(task.get("from_hand"))
                to_hand = self._normalize_hand(task.get("to_hand"))

                if from_hand is None or to_hand is None or from_hand == to_hand:
                    return planned_tasks, float("inf")

                if hand_holding.get(from_hand) is None:
                    return planned_tasks, float("inf")

                if hand_holding.get(to_hand) is not None:
                    return planned_tasks, float("inf")

                obj_name = hand_holding.get(from_hand)
                hand_holding[from_hand] = None
                hand_holding[to_hand] = obj_name

                end_time = schedule_action(
                    task,
                    "HANDOVER",
                    from_hand,
                    task_location_id,
                    obj_name,
                    start_time_by_deps,
                    secondary_hand=to_hand,
                )
                task_finish_times[task_id] = end_time
                continue

            end_time = schedule_action(task, action, chosen_hand, task_location_id, target_object, start_time_by_deps)
            task_finish_times[task_id] = end_time

        makespan = max(task_finish_times.values()) if task_finish_times else 0
        return planned_tasks, makespan