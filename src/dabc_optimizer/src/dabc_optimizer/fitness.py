import sys
import os
import heapq
import copy
import json
import threading
from datetime import datetime, timezone

try:
    from dotenv import load_dotenv
except Exception:
    load_dotenv = None

try:
    from openai import OpenAI
except Exception:
    OpenAI = None

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../task_manager/src')))
from task_module.topology_map import TopologicalMap
from task_module.domain_catalog import (
    ACTION_CATALOG,
    ACTION_EXECUTION_TIME_SEC,
    LOCATION_DISTANCE_EDGES_M,
    OBJECT_CATALOG,
    OPERABLE_LOCATIONS,
    get_object_risk_coef,
)

_topo = TopologicalMap()

# ============================================================
# 固定動作時間表 (秒) — 不依賴 LLM 的 estimated_duration
# 直接引用 domain_catalog，避免時間數值重複維護。
# ============================================================
ACTION_DURATION = {}
for action_item in ACTION_CATALOG:
    action_id = action_item.get("id")
    signature = str(action_item.get("signature", ""))
    action_name = signature.split("(", 1)[0].strip().upper()
    if action_name and action_id in ACTION_EXECUTION_TIME_SEC:
        ACTION_DURATION[action_name] = ACTION_EXECUTION_TIME_SEC[action_id]

DEFAULT_ACTION_DURATION = ACTION_DURATION.get("WAIT", 60)
FREE_HAND_REQUIRED_ACTIONS = {"WATER_DISPENSER", "OPEN_CABINET", "CLOSE_CABINET"}
SCHEDULER_HELPER_ACTIONS = {"HANDOVER", "STORE_ON_TRAY", "RETRIEVE_FROM_TRAY"}


def _format_operable_locations_table():
    header = ["| ID | Chinese | English |", "|----|---------|---------|"]
    rows = [
        f"| {loc['location_id']:>2} | {loc.get('zh_name', '')} | {loc.get('location_name', '')} |"
        for loc in OPERABLE_LOCATIONS
    ]
    return "\n".join(header + rows)


def _format_action_lines_for_scan_llm():
    lines = []
    for action in ACTION_CATALOG:
        signature = str(action.get("signature", "")).strip()
        action_name = signature.split("(", 1)[0].strip().upper()
        if action_name in SCHEDULER_HELPER_ACTIONS:
            continue
        lines.append(f"{action['id']}. `{signature}`: {action.get('description', '')}")
    return "\n".join(lines)


def _format_object_lines_for_scan_llm():
    return "\n".join(
        [
            f"- `{obj.get('zh_name', '')}` / `{obj.get('object_name', '')}` "
            f"(default location_id={obj.get('location_id')})"
            for obj in OBJECT_CATALOG
        ]
    )


def _build_scan_followup_system_prompt():
    operable_location_ids = [loc["location_id"] for loc in OPERABLE_LOCATIONS]
    min_location_id = min(operable_location_ids)
    max_location_id = max(operable_location_ids)

    return f"""
You are a runtime scan replan generator for a dual-arm robot scheduler simulation.

You will receive:
1) Scan task metadata
2) The visible object list from SCAN_TABLE_OBJECTS (`visible_objects`)
3) Original task description/instruction text

Your output must ONLY contain follow-up subtasks after scan, not the scan step itself.

Rules:
- Do NOT generate MOVE_TO.
- Respect visible_objects and instruction intent. Do not invent unrelated branches.
- Use canonical object names from the object catalog.
- Do NOT generate scheduler helper actions: HANDOVER, STORE_ON_TRAY, RETRIEVE_FROM_TRAY.
- location_id must be an integer in [{min_location_id}, {max_location_id}].
- Dependencies use local step ids among follow-ups (for example step 3 depends on [1,2]).
- Keep `hand_used = null` unless strict action rule requires hand.

Action Catalog:
{_format_action_lines_for_scan_llm()}

Operable Locations:
{_format_operable_locations_table()}

Object Catalog:
{_format_object_lines_for_scan_llm()}

Output JSON format:
{{
  "subtasks": [
    {{
      "step_id": 1,
      "action_type": "PICK",
      "target_object": "remote_control",
      "location_id": 3,
      "hand_used": null,
      "dependencies": [],
      "description": "..."
    }}
  ]
}}
"""


SCAN_FOLLOWUP_SYSTEM_PROMPT = _build_scan_followup_system_prompt()

class TaskScheduler:
    _SCAN_CUP_NAMES = {"cup", "green_cup", "water_cup", "drink_cup"}

    def __init__(self, task_lookup, w1=1.0, w2=1.0, w3=1.0, w4=1.0):
        """
        :param task_lookup: 字典格式 {id: {duration, hand, deps, action_type, location_id, ...}}
        """
        self.tasks = task_lookup
        self.tray_capacity = 1
        self.w1 = float(w1)
        self.w2 = float(w2)
        self.w3 = float(w3)
        self.w4 = float(w4)
        self.valid_location_ids = set(getattr(_topo, "locations", {}).keys())
        self.scan_llm_model = os.getenv("SCAN_FOLLOWUP_LLM_MODEL", "gpt-4o")
        self.scan_followup_cache = {}
        self.scan_llm_client = self._init_scan_llm_client()
        self.scan_followup_dump_path = os.getenv(
            "SCAN_FOLLOWUP_TASKS_JSON_PATH",
            os.path.abspath(
                os.path.join(
                    os.path.dirname(__file__),
                    "..",
                    "..",
                    "..",
                    "task_manager",
                    "scan_followup_tasks.json",
                )
            ),
        )
        self._scan_followup_dump_lock = threading.Lock()

        # 距離圖 (雙向)；與時間圖分離，供 fitness 的 distance / risk 項使用。
        self.distance_graph = {}
        for src_id, dst_id, dist_m in LOCATION_DISTANCE_EDGES_M:
            self.distance_graph.setdefault(src_id, {})[dst_id] = float(dist_m)
            self.distance_graph.setdefault(dst_id, {})[src_id] = float(dist_m)

    @staticmethod
    def _init_scan_llm_client():
        if OpenAI is None:
            return None
        candidate_env_paths = [
            os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".env")),
            os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "task_manager", ".env")),
        ]
        for env_path in candidate_env_paths:
            if os.path.isfile(env_path) and load_dotenv is not None:
                load_dotenv(dotenv_path=env_path)

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return None
        return OpenAI(api_key=api_key)

    @staticmethod
    def _build_initial_object_locations():
        """Initialize mutable object locations from domain OBJECT_CATALOG."""
        object_locations = {}
        for obj in OBJECT_CATALOG:
            name = str(obj.get("object_name", "")).strip().lower()
            if not name:
                continue
            try:
                location_id = int(obj.get("location_id"))
            except Exception:
                continue
            # Keep first configured location as canonical initial state.
            object_locations.setdefault(name, location_id)
        return object_locations

    @staticmethod
    def _scan_visible_objects(object_locations, location_id):
        """Return sorted object names currently located at the given location."""
        visible = [name for name, loc in object_locations.items() if int(loc) == int(location_id)]
        visible.sort()
        return visible

    def _normalize_scan_followup_tasks(self, scan_task_id, scan_task, raw_subtasks):
        if not isinstance(raw_subtasks, list):
            return []

        parent_id = scan_task.get("parent_id")
        urgency_level = scan_task.get("urgency_level", "normal")
        urgency_score = scan_task.get("urgency_score", 0)

        cleaned = []
        for idx, sub in enumerate(raw_subtasks, start=1):
            if not isinstance(sub, dict):
                continue

            action_type = str(sub.get("action_type", "")).strip().upper()
            if not action_type or action_type in SCHEDULER_HELPER_ACTIONS or action_type == "MOVE_TO":
                continue

            try:
                local_step = int(sub.get("step_id", idx))
            except Exception:
                local_step = idx

            location_id = self._sanitize_location_id(sub.get("location_id", scan_task.get("location_id", 1)), scan_task.get("location_id", 1))
            target_object = sub.get("target_object")
            deps = list(sub.get("dependencies", []) or [])
            hand_used = self._normalize_hand(sub.get("hand_used"))

            cleaned.append(
                {
                    "_local_step": local_step,
                    "_raw_dependencies": deps,
                    "action_type": action_type,
                    "target_object": target_object,
                    "location_id": int(location_id),
                    "hand_used": hand_used,
                    "description": str(sub.get("description", "")).strip() or "[SIM] LLM-generated scan follow-up.",
                    "estimated_duration": int(ACTION_DURATION.get(action_type, DEFAULT_ACTION_DURATION)),
                    "urgency_level": urgency_level,
                    "urgency_score": urgency_score,
                    "parent_id": parent_id,
                }
            )

        if not cleaned:
            return []

        cleaned.sort(key=lambda item: item["_local_step"])
        local_to_global = {}
        for idx, item in enumerate(cleaned, start=1):
            item["global_id"] = f"{scan_task_id}__sim_{idx}"
            local_to_global[item["_local_step"]] = item["global_id"]

        for item in cleaned:
            mapped_deps = []
            for dep in item.get("_raw_dependencies", []):
                if isinstance(dep, str) and dep == scan_task_id:
                    mapped_deps.append(scan_task_id)
                    continue
                try:
                    dep_local = int(dep)
                except Exception:
                    continue
                dep_global = local_to_global.get(dep_local)
                if dep_global:
                    mapped_deps.append(dep_global)

            if not mapped_deps:
                mapped_deps = [scan_task_id]
            elif scan_task_id not in mapped_deps:
                mapped_deps.append(scan_task_id)

            item["dependencies"] = mapped_deps
            item.pop("_local_step", None)
            item.pop("_raw_dependencies", None)

        return cleaned

    def _append_scan_followup_dump(self, payload):
        """Persist scan-followup generation details to a JSON file for debugging."""
        if not self.scan_followup_dump_path:
            return

        try:
            log_dir = os.path.dirname(self.scan_followup_dump_path)
            if log_dir:
                os.makedirs(log_dir, exist_ok=True)

            with self._scan_followup_dump_lock:
                existing = []
                if os.path.isfile(self.scan_followup_dump_path):
                    try:
                        with open(self.scan_followup_dump_path, "r", encoding="utf-8") as f:
                            loaded = json.load(f)
                        if isinstance(loaded, list):
                            existing = loaded
                    except Exception:
                        existing = []

                existing.append(payload)
                with open(self.scan_followup_dump_path, "w", encoding="utf-8") as f:
                    json.dump(existing, f, ensure_ascii=False, indent=2)
        except Exception:
            # Debug log writing should never break planning flow.
            return

    def _build_scan_followup_tasks(self, scan_task_id, scan_task, scan_location_id, visible_objects, object_locations):
        """Generate simulation follow-up tasks with LLM based on scan result + task text."""
        if not bool(scan_task.get("runtime_replan_enabled", False)):
            return []

        instruction_text = str(scan_task.get("post_scan_instruction", "") or "").strip()
        description_text = str(scan_task.get("description", "") or "").strip()
        merged_intent = "\n".join([part for part in [instruction_text, description_text] if part]).strip()
        if not merged_intent:
            return []

        visible_list = sorted({str(obj).strip().lower() for obj in (visible_objects or []) if str(obj).strip()})
        cache_key = (
            scan_task_id,
            int(scan_location_id),
            merged_intent,
            tuple(visible_list),
        )
        if cache_key in self.scan_followup_cache:
            return copy.deepcopy(self.scan_followup_cache[cache_key])

        if self.scan_llm_client is None:
            return []

        scan_payload = {
            "scan_task_id": scan_task_id,
            "scan_location_id": int(scan_location_id),
            "parent_id": scan_task.get("parent_id"),
            "urgency_level": scan_task.get("urgency_level", "normal"),
            "urgency_score": scan_task.get("urgency_score", 0),
            "task_description": description_text,
            "post_scan_instruction": instruction_text,
            "visible_objects": visible_list,
            "object_locations_at_sim": {
                name: int(loc)
                for name, loc in (object_locations or {}).items()
            },
        }

        try:
            response = self.scan_llm_client.chat.completions.create(
                model=self.scan_llm_model,
                messages=[
                    {"role": "system", "content": SCAN_FOLLOWUP_SYSTEM_PROMPT},
                    {"role": "user", "content": json.dumps(scan_payload, ensure_ascii=False)},
                ],
                temperature=0.0,
                response_format={"type": "json_object"},
            )
            content = response.choices[0].message.content
            parsed = json.loads(content)
        except Exception as exc:
            self._append_scan_followup_dump(
                {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "scan_task_id": scan_task_id,
                    "scan_location_id": int(scan_location_id),
                    "visible_objects": visible_list,
                    "task_description": description_text,
                    "post_scan_instruction": instruction_text,
                    "llm_raw_subtasks": [],
                    "normalized_subtasks": [],
                    "error": str(exc),
                }
            )
            return []

        normalized = self._normalize_scan_followup_tasks(
            scan_task_id=scan_task_id,
            scan_task=scan_task,
            raw_subtasks=parsed.get("subtasks", []),
        )

        self._append_scan_followup_dump(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "scan_task_id": scan_task_id,
                "scan_location_id": int(scan_location_id),
                "visible_objects": visible_list,
                "task_description": description_text,
                "post_scan_instruction": instruction_text,
                "llm_raw_subtasks": parsed.get("subtasks", []),
                "normalized_subtasks": normalized,
                "error": None,
            }
        )

        self.scan_followup_cache[cache_key] = copy.deepcopy(normalized)
        return normalized

    def calculate_makespan(self, sequence):
        """
        計算 Makespan，同時考慮：
        1. 依賴關係 (Dependency)
        2. 手臂容量狀態 (Hand Capacity) - 避免滿手時還去抓東西
        3. 隱性移動成本 (Implicit Travel Cost) - 根據前後任務的 location_id 自動計算移動時間
        """
        _, makespan = self._simulate(sequence, record_actions=False)
        return makespan

    def calculate_fitness(self, sequence):
        sim_result = self._simulate(sequence, record_actions=False, return_metrics=True)
        if len(sim_result) == 2:
            _, makespan = sim_result
            if makespan == float("inf"):
                return float("inf")
            return float("inf")

        _, makespan, metrics = sim_result

        if makespan == float("inf"):
            return float("inf")

        time_cost = makespan
        distance_cost = metrics["travel_distance"]
        delay_penalty = metrics["delay_penalty"]
        risk_penalty = metrics["risk_penalty"]

        return (
            self.w1 * time_cost
            + self.w2 * distance_cost
            + self.w3 * delay_penalty
            + self.w4 * risk_penalty
        )

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

    def _choose_storeable_hand_to_tray(self, hand_holding, resource_clock):
        """Tray accepts any object; pick one occupied hand to free up."""
        return self._choose_hand_to_store(hand_holding, resource_clock)

    def _sanitize_location_id(self, location_id, fallback_location_id):
        """Return a valid location id; fallback to current location when invalid."""
        try:
            loc = int(location_id)
        except Exception:
            return fallback_location_id
        if loc in self.valid_location_ids:
            return loc
        return fallback_location_id

    def _simulate(self, sequence, record_actions=False, return_metrics=False):
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

        # Mutable simulated world-state used by SCAN / PICK / PLACE.
        # location_id == 0 means currently on robot (in hand or tray).
        object_locations = self._build_initial_object_locations()

        current_location_id = 1
        task_finish_times = {}
        planned_tasks = []
        insert_seq = 0

        total_travel_distance = 0.0
        total_delay_penalty = 0.0
        total_risk_penalty = 0.0

        def _shortest_distance(start_id, end_id):
            if start_id == end_id:
                return 0.0

            if end_id in self.distance_graph.get(start_id, {}):
                return self.distance_graph[start_id][end_id]

            # Dijkstra on distance graph for non-adjacent locations.
            pq = [(0.0, start_id)]
            best = {start_id: 0.0}
            while pq:
                cur_dist, cur_node = heapq.heappop(pq)
                if cur_node == end_id:
                    return cur_dist
                if cur_dist > best.get(cur_node, float("inf")):
                    continue
                for nxt, edge_d in self.distance_graph.get(cur_node, {}).items():
                    nd = cur_dist + edge_d
                    if nd < best.get(nxt, float("inf")):
                        best[nxt] = nd
                        heapq.heappush(pq, (nd, nxt))
            return float("inf")

        def _current_carry_risk_coef(hand_holding_state, tray_state):
            risk_sum = 0.0
            for obj in hand_holding_state.values():
                if obj:
                    risk_sum += float(get_object_risk_coef(obj, 0))
            for obj in tray_state:
                if obj:
                    risk_sum += float(get_object_risk_coef(obj, 0))
            return risk_sum

        def schedule_action(task_payload, action_type, hand, location_id, target_object, min_start_time, travel_risk_coef=0.0, is_synthetic=False, secondary_hand=None, extra_task_fields=None):
            nonlocal current_location_id, total_travel_distance, total_delay_penalty, total_risk_penalty

            action_duration = ACTION_DURATION.get(
                action_type,
                task_payload.get("estimated_duration", DEFAULT_ACTION_DURATION) if task_payload else DEFAULT_ACTION_DURATION,
            )

            travel_time = _topo.get_travel_time(current_location_id, location_id)
            travel_distance = _shortest_distance(current_location_id, location_id)
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

            total_travel_distance += travel_distance
            total_risk_penalty += travel_distance * float(travel_risk_coef)

            priority_coef = 0.0
            if task_payload:
                raw_priority = task_payload.get("urgency_score", 0)
                try:
                    priority_coef = float(raw_priority)
                except Exception:
                    priority_coef = 0.0
            total_delay_penalty += end_time * 0.01 * priority_coef

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
                if isinstance(extra_task_fields, dict) and extra_task_fields:
                    task_data.update(extra_task_fields)
                if is_synthetic:
                    task_data.setdefault("description", f"Auto-inserted {action_type} for tray handling.")
                planned_tasks.append(task_data)

            return end_time

        local_tasks = dict(self.tasks)
        execution_queue = list(sequence)
        expanded_scan_tasks = set()

        while execution_queue:
            task_id = execution_queue.pop(0)
            if task_id not in local_tasks:
                return planned_tasks, float("inf")

            task = local_tasks[task_id]
            action = task.get("action_type", "PICK")
            raw_location_id = task.get("location_id", current_location_id)
            task_location_id = self._sanitize_location_id(raw_location_id, current_location_id)
            target_object = task.get("target_object")

            # === 檢查 A: 依賴關係 (Dependency Check) ===
            start_time_by_deps = 0
            for dep_id in task.get("dependencies", []):
                if dep_id not in task_finish_times:
                    return planned_tasks, float("inf")
                start_time_by_deps = max(start_time_by_deps, task_finish_times[dep_id])

            normalized_hand = self._normalize_hand(task.get("hand_used"))
            base_move_risk = _current_carry_risk_coef(hand_holding, tray_contents)

            if action == "SCAN_TABLE_OBJECTS":
                visible_objects = self._scan_visible_objects(object_locations, task_location_id)
                end_time = schedule_action(
                    task,
                    action,
                    None,
                    task_location_id,
                    target_object,
                    start_time_by_deps,
                    travel_risk_coef=base_move_risk,
                    extra_task_fields={"simulated_scan_objects": visible_objects},
                )
                task_finish_times[task_id] = end_time

                if task_id not in expanded_scan_tasks:
                    followups = self._build_scan_followup_tasks(
                        task_id,
                        task,
                        task_location_id,
                        visible_objects,
                        object_locations,
                    )
                    if followups:
                        inserted_ids = []
                        for follow_task in followups:
                            follow_id = follow_task["global_id"]
                            local_tasks[follow_id] = follow_task
                            inserted_ids.append(follow_id)

                        for follow_id in reversed(inserted_ids):
                            execution_queue.insert(0, follow_id)

                expanded_scan_tasks.add(task_id)
                continue

            if action in FREE_HAND_REQUIRED_ACTIONS:
                if hand_holding.get("Left_Arm") is not None and hand_holding.get("Right_Arm") is not None:
                    if len(tray_contents) >= self.tray_capacity:
                        return planned_tasks, float("inf")

                    hand_to_store = self._choose_storeable_hand_to_tray(hand_holding, resource_clock)
                    if hand_to_store is None:
                        return planned_tasks, float("inf")

                    stored_obj = hand_holding.get(hand_to_store)
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
                        travel_risk_coef=_current_carry_risk_coef(hand_holding, tray_contents),
                        is_synthetic=True,
                    )
                    tray_contents.append(stored_obj)
                    hand_holding[hand_to_store] = None
                    if stored_obj:
                        object_locations[stored_obj] = 0
                    task_finish_times[store_task_payload["global_id"]] = end_time

            if not self._action_requires_hand(action):
                end_time = schedule_action(task, action, None, task_location_id, target_object, start_time_by_deps, travel_risk_coef=base_move_risk)
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
                                travel_risk_coef=_current_carry_risk_coef(hand_holding, tray_contents),
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

                    hand_to_store = self._choose_storeable_hand_to_tray(hand_holding, resource_clock)
                    if hand_to_store is None:
                        return planned_tasks, float("inf")

                    stored_obj = hand_holding.get(hand_to_store)
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
                        travel_risk_coef=_current_carry_risk_coef(hand_holding, tray_contents),
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
                picked_obj = self._parse_object_name(target_object) or "HOLDING_SOMETHING"

                # Simulation policy for scheduling-efficiency evaluation:
                # If default location and task location differ, trust the task location
                # for this run and sync object state to that location before PICK.
                # This avoids false infeasible plans caused by stale defaults.
                known_loc = object_locations.get(picked_obj)
                if known_loc is None:
                    object_locations[picked_obj] = int(task_location_id)
                elif int(known_loc) not in (0, int(task_location_id)):
                    object_locations[picked_obj] = int(task_location_id)

                end_time = schedule_action(task, action, chosen_hand, task_location_id, target_object, start_time_by_deps, travel_risk_coef=base_move_risk)
                hand_holding[chosen_hand] = picked_obj
                object_locations[picked_obj] = 0
                task_finish_times[task_id] = end_time
                continue

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
                        travel_risk_coef=_current_carry_risk_coef(hand_holding, tray_contents),
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

                end_time = schedule_action(task, action, chosen_hand, task_location_id, target_object, start_time_by_deps, travel_risk_coef=base_move_risk)
                hand_holding[chosen_hand] = None
                if obj_name:
                    object_locations[obj_name] = int(task_location_id)
                task_finish_times[task_id] = end_time
                continue

            elif action == "STORE_ON_TRAY":
                if len(tray_contents) >= self.tray_capacity:
                    return planned_tasks, float("inf")

                obj_name = self._parse_object_name(target_object)
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
                end_time = schedule_action(task, action, chosen_hand, task_location_id, target_object, start_time_by_deps, travel_risk_coef=base_move_risk)
                tray_contents.append(stored_obj)
                hand_holding[chosen_hand] = None
                if stored_obj:
                    object_locations[stored_obj] = 0
                task_finish_times[task_id] = end_time
                continue

            elif action == "RETRIEVE_FROM_TRAY":
                obj_name = self._parse_object_name(target_object)
                if obj_name and obj_name not in tray_contents:
                    return planned_tasks, float("inf")

                if chosen_hand is None:
                    chosen_hand = self._choose_available_hand(allowed_hands, hand_holding, resource_clock, start_time_by_deps)

                if chosen_hand is None or hand_holding.get(chosen_hand) is not None:
                    return planned_tasks, float("inf")

                end_time = schedule_action(task, action, chosen_hand, task_location_id, target_object, start_time_by_deps, travel_risk_coef=base_move_risk)
                if obj_name:
                    tray_contents.remove(obj_name)
                    hand_holding[chosen_hand] = obj_name
                    object_locations[obj_name] = 0
                else:
                    if not tray_contents:
                        return planned_tasks, float("inf")
                    picked_from_tray = tray_contents.pop(0)
                    hand_holding[chosen_hand] = picked_from_tray
                    if picked_from_tray:
                        object_locations[picked_from_tray] = 0
                task_finish_times[task_id] = end_time
                continue

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
                        travel_risk_coef=_current_carry_risk_coef(hand_holding, tray_contents),
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

                end_time = schedule_action(
                    task,
                    "HANDOVER",
                    from_hand,
                    task_location_id,
                    obj_name,
                    start_time_by_deps,
                    travel_risk_coef=base_move_risk,
                    secondary_hand=to_hand,
                )
                hand_holding[from_hand] = None
                hand_holding[to_hand] = obj_name
                if obj_name:
                    object_locations[obj_name] = 0
                task_finish_times[task_id] = end_time
                continue

            end_time = schedule_action(task, action, chosen_hand, task_location_id, target_object, start_time_by_deps, travel_risk_coef=base_move_risk)
            task_finish_times[task_id] = end_time

        makespan = max(task_finish_times.values()) if task_finish_times else 0
        if return_metrics:
            return planned_tasks, makespan, {
                "travel_distance": total_travel_distance,
                "delay_penalty": total_delay_penalty,
                "risk_penalty": total_risk_penalty,
            }
        return planned_tasks, makespan