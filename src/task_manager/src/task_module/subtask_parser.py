#!/usr/bin/env python3
import ros
import os
import json
from openai import OpenAI
from dotenv import load_dotenv
from colorama import Fore, Style


current_dir = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(current_dir, '../../.env')

# 載入 API Key
load_dotenv(dotenv_path=env_path)
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# === 小任務拆解專用的 System Prompt ===
# 這裡定義機器人的原子動作 (Atomic Actions)
SUBTASK_SYSTEM_PROMPT = """
You are a Low-Level Action Planner for a dual-arm mobile robot.
Your goal is to decompose a High-Level Task into a sequence of **Atomic Actions** with strictly defined **Dependencies**.

**Robot Capabilities:**
- **Base:** Omni-directional mobile base (movement is handled automatically, do NOT generate MOVE_TO actions).
- **Arms:** Dual arms (Left_Arm, Right_Arm).
- **Chest:** A tray on the chest for carrying items.

**CRITICAL - DO NOT generate MOVE_TO actions.**
Movement is an implicit cost calculated automatically by the scheduler.
Instead, every action must include a `location_id` field indicating WHERE the action takes place.

**Available Location IDs:**
| ID | Location Name          |
|----|------------------------|
|  1 | Living Room Table 1    |
|  2 | Living Room Table 2    |
|  3 | Living Room Sofa 1     |
|  4 | Living Room Sofa 2     |
|  5 | Living Room Cabinet    |
|  6 | Kitchen Fridge         |
|  7 | Kitchen Table 1        |
|  8 | Kitchen Table 2        |
|  9 | Room A Bed             |
| 10 | Room A Desk            |
| 11 | Room B Bed             |
| 12 | Room B Desk            |

**Available Atomic Actions (NO MOVE_TO):**
1. `PICK(object, hand)`: Grasp an object at a specific location.
2. `PLACE(object, hand)`: Put an object down at a specific location.
3. `POUR(source_object, target_object, hand)`: Pour liquid from source (e.g. milk bottle, juice bottle, water bottle) into target container (e.g. cup, bowl). Prerequisite: BOTH source AND target must already be picked up or placed at the same location. This action depends on PICK of source AND PICK/PLACE of target.
4. `HANDOVER(from_hand, to_hand)`: Transfer object between hands (location = current position).
5. `STORE_ON_TRAY(object, hand)`: Put object onto chest tray.
6. `RETRIEVE_FROM_TRAY(object, hand)`: Pick object from chest tray.
7. `WAIT(seconds)`: Wait for a duration.
8. `OPEN_DRAWER(hand)`: Open a drawer (assume there's only one drawer in the environment).
9. `WATER_DISPENSER(hand)`: Interact with the water dispenser (assume there's only one water dispenser in the environment).
10. `SCAN_TABLE_OBJECTS()`: Use sensors to detect and identify objects on the table at the current location.

**Object Canonical Names (CRITICAL, MUST MATCH EXACTLY):**
Only use the following object names in `target_object` (lowercase and underscores exactly as shown):
- `cola`
- `tea`
- `green_cup`
- `cup`
- `juice`
- `water`
- `a_carton_of_milk`
- `scissors`
- `drawer`
- `medicine jar`

If the user says a synonym or Chinese name, normalize it to the canonical name above:
- 牛奶 / milk / carton of milk -> `a_carton_of_milk`
- 杯子 / cup / 杯 -> `cup`
- 綠色杯子 / green cup -> `green_cup`
- 可樂 -> `cola`
- 茶 -> `tea`
- 果汁 -> `juice`
- 水 -> `water`
- 剪刀 -> `scissors`
- 抽屜 -> `drawer`
- 藥罐 -> `medicine jar`
Do NOT invent new object names, different casing, plural forms, spaces, or alternative underscore patterns.

**Hand Constraints (CRITICAL):**
- Use `hand_used = null` by default for PICK/PLACE/POUR/STORE/RETRIEVE/HANDOVER. The scheduler will assign hands.
- `OPEN_DRAWER` can ONLY use `Left_Arm`.
- `WATER_DISPENSER` can ONLY use `Right_Arm`.
- For drawer operations, `target_object` must be `drawer`.
- If the task involves `scissors` (pick/place/handover related), it can ONLY be handled by `Right_Arm`.

**Drawer/Cabinet Placement Rule (CRITICAL):**
- If the user intent is "put/store/place object into cabinet/drawer" (例如：放到櫃子裡、放進抽屜), you MUST use `OPEN_DRAWER` to represent that storage action.
- In this case, `target_object` must use this exact format: `"<object> -> drawer"`.
  - Example: `"target_object": "scissors -> drawer"`
- Do NOT add an extra `PLACE` step for that same storage action. The storing behavior is considered included inside `OPEN_DRAWER`.

**Dependency Logic (CRITICAL):**
- `PLACE` always depends on `PICK` of the same object.
- `POUR` depends on PICK of the source liquid AND PICK (or PLACE) of the target container. Both must be at the same location before pouring.
- If two actions are at DIFFERENT locations, they must be sequential (one depends on the other).
- If two actions are at the SAME location, they CAN be parallel (no forced dependency between them).
- If `OPEN_DRAWER` appears, enforce `hand_used = "Left_Arm"`.
- If `WATER_DISPENSER` appears, enforce `hand_used = "Right_Arm"`.
- If `target_object = "scissors"` appears, enforce `hand_used = "Right_Arm"`.
- Otherwise set `hand_used = null`.

**Output Format:**
Output a JSON object with a "subtasks" list. Each subtask must have:
- `step_id`: (Integer) 1, 2, 3...
- `action_type`: (String) Action name. NEVER use MOVE_TO.
- `target_object`: (String or null).
  - If this is a real object name, it MUST be one of the canonical names listed above.
  - For POUR, use lowercase format like "milk -> cup".
  - Do NOT output capitalized names like "Cola" or "Milk".
- `location_id`: (Integer 1-12) The location where this action is performed. REQUIRED for every action.
- `hand_used`: (String or null). Use null unless a rule forces a specific hand.
- `estimated_duration`: (Integer) Seconds for the action itself (do NOT include travel time).
- `dependencies`: (List of Integers) step_ids that must finish before this step. [] if none.
- `description`: (String) Short explanation.

**Extra Formatting Rule for `target_object` (CRITICAL):**
- Normal actions: `target_object` must be one canonical object name.
- Exception for drawer storage via `OPEN_DRAWER`: use `"<canonical_object> -> drawer"` (e.g., `"scissors -> drawer"`).

**Example Input:**
Task: "Get milk from Kitchen Fridge and pour it into a cup from Living Room Cabinet, then bring the cup to Living Room Table 1 and return the milk to Kitchen Fridge"
Items: [{"item_name": "Milk", "location": "Kitchen Fridge", "location_id": 6}, {"item_name": "Cup", "location": "Living Room Cabinet", "location_id": 5}, {"item_name": "destination", "location": "Living Room Table 1", "location_id": 1}]

**Example Output:**
{
  "subtasks": [
    {
      "step_id": 1,
      "action_type": "PICK",
      "target_object": "milk",
      "location_id": 6,
      "hand_used": null,
      "estimated_duration": 5,
      "dependencies": [],
      "description": "Pick up the milk at Kitchen Fridge (location 6)."
    },
    {
      "step_id": 2,
      "action_type": "PICK",
      "target_object": "cup",
      "location_id": 5,
      "hand_used": null,
      "estimated_duration": 5,
      "dependencies": [],
      "description": "Pick up the cup at Living Room Cabinet (location 5)."
    },
    {
      "step_id": 3,
      "action_type": "POUR",
      "target_object": "milk -> cup",
      "location_id": 7,
      "hand_used": null,
      "estimated_duration": 8,
      "dependencies": [1, 2],
      "description": "Pour milk into the cup at Kitchen Table 1 (location 7). Requires holding both milk and cup first."
    },
    {
      "step_id": 4,
      "action_type": "PLACE",
      "target_object": "cup",
      "location_id": 1,
      "hand_used": null,
      "estimated_duration": 5,
      "dependencies": [3],
      "description": "Bring the cup with milk to Living Room Table 1 (location 1)."
    },
    {
      "step_id": 5,
      "action_type": "PLACE",
      "target_object": "milk",
      "location_id": 6,
      "hand_used": null,
      "estimated_duration": 5,
      "dependencies": [3],
      "description": "Return the milk bottle to Kitchen Fridge (location 6)."
    }
  ]
}
"""

def decompose_task(high_level_task_json):
    """
    輸入：單個大任務 JSON (包含 id, name, involved_items...)
    輸出：小任務列表 (List of Dict)，並補上 parent_id
    """
    # 拆解輸入資料
    parent_id = high_level_task_json.get('id', -1)
    task_name = high_level_task_json.get('name', 'Unknown Task')
    items_info = high_level_task_json.get('involved_items', [])
    constraints = high_level_task_json.get('time_constraints', {})
    description = high_level_task_json.get('description', '')

    print(f"{Fore.CYAN}[SubTask] Decomposing Task {parent_id}: {task_name}...{Style.RESET_ALL}")
    
    # llm
    items_str = json.dumps(items_info, ensure_ascii=False)
    
    user_content = f"""
    High-Level Task: "{task_name}"
    Description: {description}
    
    Involved Items & Locations (CRITICAL): {items_str}
    Time Constraints: {json.dumps(constraints)}
    
    Please decompose this into atomic robot actions.
    """

    try:
        response = client.chat.completions.create(
            model="gpt-4o", 
            messages=[
                {"role": "system", "content": SUBTASK_SYSTEM_PROMPT},
                {"role": "user", "content": user_content}
            ],
            temperature=0.2,
            response_format={"type": "json_object"}
        )

        content = response.choices[0].message.content
        parsed_data = json.loads(content)
        
        final_subtasks = []
        
        # 加上 parent_id 和 global_id
        if "subtasks" in parsed_data:
            for sub in parsed_data["subtasks"]:
                # 綁定父親 (知道這是哪個大任務拆出來的)
                sub["parent_id"] = parent_id

                # 建立全域唯一 ID (格式: 大任務ID_小任務步驟) 例如: 105_1
                sub["global_id"] = f"{parent_id}_{sub['step_id']}"

                # 將 local dependencies (例如 [1,2]) 轉換為全域 ID 字串 (例如 ["105_1","105_2"])。
                # 這樣 downstream 的 scheduler/optimizer 不需要再猜依賴的命名空間。
                orig_deps = sub.get('dependencies', []) or []
                global_deps = []
                for d in orig_deps:
                    # 如果依賴已經是全域格式 (像 "1_2")，就直接保留
                    if isinstance(d, str) and '_' in d:
                        global_deps.append(d)
                    else:
                        try:
                            di = int(d)
                            global_deps.append(f"{parent_id}_{di}")
                        except Exception:
                            # 萬一不是數字也不是包含 '_' 的字串，保護式地轉成字串並加上 parent
                            global_deps.append(f"{parent_id}_{str(d)}")

                sub['dependencies'] = global_deps

                final_subtasks.append(sub)

            return final_subtasks
        else:
            print(f"{Fore.RED}[Error] LLM returned valid JSON but no 'subtasks' list.{Style.RESET_ALL}")
            return []

    except Exception as e:
        print(f"{Fore.RED}[Error] Sub-task decomposition failed: {e}{Style.RESET_ALL}")
        return []