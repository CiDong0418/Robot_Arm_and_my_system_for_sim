#!/usr/bin/env python3
import ros
import os
import json
from openai import OpenAI
from dotenv import load_dotenv
from colorama import Fore, Style

from task_module.domain_catalog import ACTION_CATALOG, OBJECT_CATALOG, OPERABLE_LOCATIONS


current_dir = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(current_dir, '../../.env')

# 載入 API Key
load_dotenv(dotenv_path=env_path)
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def _format_operable_locations_table():
    header = ["| ID | 中文名稱 | English Name |", "|----|--------|--------------|"]
    rows = [
        f"| {loc['location_id']:>2} | {loc['zh_name']} | {loc['location_name']} |"
        for loc in OPERABLE_LOCATIONS
    ]
    return "\n".join(header + rows)


def _format_action_lines():
    return "\n".join(
        [
            f"{action['id']}. `{action['signature']}`: {action['description']}"
            for action in ACTION_CATALOG
        ]
    )


def _format_object_lines():
    return "\n".join(
        [
            f"- `{obj['zh_name']}` / `{obj['object_name']}` (default: {obj['location_name']} / location_id={obj['location_id']})"
            for obj in OBJECT_CATALOG
        ]
    )


def _build_subtask_system_prompt():
    operable_location_ids = [loc["location_id"] for loc in OPERABLE_LOCATIONS]
    min_location_id = min(operable_location_ids)
    max_location_id = max(operable_location_ids)

    return f"""
You are a Low-Level Action Planner for a dual-arm mobile robot.
Your goal is to decompose a High-Level Task into a sequence of **Atomic Actions** with strictly defined **Dependencies**.

**Robot Capabilities:**
- **Base:** Omni-directional mobile base (movement is handled automatically, do NOT generate MOVE_TO actions).
- **Arms:** Dual arms (Left_Arm, Right_Arm).
- **Chest:** A tray on the chest for carrying items.

**CRITICAL - DO NOT generate MOVE_TO actions.**
Movement is an implicit cost calculated automatically by the scheduler.
Instead, every action must include a `location_id` field indicating WHERE the action takes place.

**Reachable and Operable Locations (single source of truth):**
{_format_operable_locations_table()}

**Available Atomic Actions (NO MOVE_TO, single source of truth):**
{_format_action_lines()}

**Object Catalog with Default Locations (single source of truth):**
{_format_object_lines()}

**Object Canonical Names (CRITICAL, MUST MATCH EXACTLY):**
Only use the English object names from the object catalog above in `target_object`.
Chinese input should be normalized to the corresponding English name.
Use lowercase with exact underscores as defined (for example: `milk`, `medicine_jar`, `wet_wipe`).

If the user says a synonym or Chinese name, normalize it to canonical names:
- milk / carton of milk / 牛奶 -> `milk`
- juice / 果汁 -> `juice`
- cola / 可樂 -> `cola`
- water cup / 水杯 -> `water_cup`
- drink cup / 飲料杯 -> `drink_cup`
- mineral water / 礦泉水 -> `mineral_water`
- apple / 蘋果 -> `apple`
- banana / 香蕉 -> `banana`
- orange / 橘子 -> `orange`
- cookie / 餅乾 -> `cookie`
- lemon / 檸檬 -> `lemon`
- tissue box / 衛生紙 -> `tissue_box`
- wet wipe / 濕紙巾 -> `wet_wipe`
- remote control / 遙控器 -> `remote_control`
- medicine_jar / 藥罐 -> `medicine_jar`
- pen / 原子筆 -> `pen`
- notebook / 筆記本 -> `notebook`
- glasses case / 眼鏡盒 -> `glasses_case`
- scissors / 剪刀 -> `scissors`
- tape / 膠帶 -> `tape`
- utility knife / 美工刀 -> `utility_knife`
- scrub sponge / 菜瓜布 -> `scrub_sponge`
- hand soap / 洗手乳 -> `hand_soap`
- salt shaker / 鹽巴罐 -> `salt_shaker`
- instant powder packet / 沖泡粉包 -> `instant_powder_packet`
- keyring / 鑰匙串 -> `keyring`
- comb / 梳子 -> `comb`
- camera / 相機 -> `camera`
- headphones / 耳機 -> `headphones`
- bowl / 碗 -> `bowl`
- cloth / 抹布 -> `cloth`
If a name is not in the catalog, do not invent a new one.
Do NOT invent new object names, different casing, plural forms, spaces, or alternative underscore patterns.

**Hand Constraints (CRITICAL):**
- Use `hand_used = null` by default for PICK/PLACE/POUR/STORE/RETRIEVE/HANDOVER/PRESS_BUTTON/WIPE_SURFACE.
- `OPEN_DRAWER` and `CLOSE_DRAWER` can ONLY use `Left_Arm`.
- `WATER_DISPENSER` can ONLY use `Right_Arm`.
- For drawer operations, `target_object` must be `drawer`.
- If the task involves `scissors` (pick/place/handover related), it can ONLY be handled by `Right_Arm`.

**Drawer/Cabinet Rules (CRITICAL):**
- If user intent is "put/store/place object into cabinet/drawer", you MUST represent storage as opening that container.
- Drawer storage format: `"<object> -> drawer"` with `OPEN_DRAWER`.
- Cabinet storage/retrieval must include `OPEN_CABINET` before the item manipulation and `CLOSE_CABINET` when leaving.
- Do NOT add an extra PLACE for the exact same drawer-storage action represented by `OPEN_DRAWER`.

**Dependency Logic (CRITICAL):**
- `PLACE` always depends on `PICK` of the same object.
- `POUR` depends on PICK of the source liquid AND PICK (or PLACE) of the target container.
- `WIPE_SURFACE` depends on PICK of `cloth` or `wet_wipe` in the same hand.
- If two actions are at different locations, they must be sequential.
- If two actions are at the same location, they can be parallel unless prerequisites force order.
- If `OPEN_DRAWER` or `CLOSE_DRAWER` appears, enforce `hand_used = "Left_Arm"`.
- If `WATER_DISPENSER` appears, enforce `hand_used = "Right_Arm"`.
- If `target_object = "scissors"` appears, enforce `hand_used = "Right_Arm"`.
- Otherwise set `hand_used = null`.

**Output Format:**
Output a JSON object with a `subtasks` list. Each subtask must have:
- `step_id`: (Integer) 1, 2, 3...
- `action_type`: (String) Action name. NEVER use MOVE_TO.
- `target_object`: (String or null).
  - If this is a real object name, it MUST be one canonical object name from the object catalog.
  - For POUR, use lowercase format like `milk -> cup`.
- `location_id`: (Integer {min_location_id}-{max_location_id}) Required for every action.
- `hand_used`: (String or null). Use null unless a rule forces a specific hand.
- `estimated_duration`: (Integer) Seconds for the action itself (do NOT include travel time).
- `dependencies`: (List of Integers) step_ids that must finish before this step. `[]` if none.
- `description`: (String) Short explanation.

**Extra Formatting Rule for `target_object` (CRITICAL):**
- Normal actions: one canonical object name from object catalog.
- Exception for drawer storage via `OPEN_DRAWER`: `"<canonical_object> -> drawer"` (for example, `"scissors -> drawer"`).

**Example Input:**
Task: "Get milk from fridge and pour it into a cup from the bar counter, then bring the cup to the dining table and return the milk to the fridge"
Items: [{{"item_name": "milk", "location": "fridge", "location_id": 7}}, {{"item_name": "cup", "location": "bar_counter", "location_id": 5}}, {{"item_name": "destination", "location": "dining_table", "location_id": 4}}]

**Example Output:**
{{
  "subtasks": [
    {{
      "step_id": 1,
      "action_type": "PICK",
      "target_object": "milk",
      "location_id": 6,
      "hand_used": null,
      "estimated_duration": 5,
      "dependencies": [],
    "description": "Pick up the milk at the fridge (location 7)."
    }},
    {{
      "step_id": 2,
      "action_type": "PICK",
      "target_object": "cup",
      "location_id": 5,
      "hand_used": null,
      "estimated_duration": 5,
      "dependencies": [],
    "description": "Pick up the cup at the bar counter (location 5)."
    }},
    {{
      "step_id": 3,
      "action_type": "POUR",
      "target_object": "milk -> cup",
    "location_id": 7,
      "hand_used": null,
      "estimated_duration": 8,
      "dependencies": [1, 2],
    "description": "Pour milk into the cup at the fridge area (location 7). Requires holding both milk and cup first."
    }},
    {{
      "step_id": 4,
      "action_type": "PLACE",
      "target_object": "cup",
    "location_id": 4,
      "hand_used": null,
      "estimated_duration": 5,
      "dependencies": [3],
    "description": "Bring the cup with milk to the dining table (location 4)."
    }},
    {{
      "step_id": 5,
      "action_type": "PLACE",
      "target_object": "milk",
    "location_id": 7,
      "hand_used": null,
      "estimated_duration": 5,
      "dependencies": [3],
    "description": "Return the milk bottle to the fridge (location 7)."
    }}
  ]
}}
"""


# === 小任務拆解專用的 System Prompt ===
SUBTASK_SYSTEM_PROMPT = _build_subtask_system_prompt()

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