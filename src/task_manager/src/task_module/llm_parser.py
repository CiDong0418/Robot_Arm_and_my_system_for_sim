import os
import json
from openai import OpenAI
from dotenv import load_dotenv
from colorama import Fore, Style

from task_module.domain_catalog import OBJECT_CATALOG, OPERABLE_LOCATIONS

# 被high_level_node.py呼叫

current_dir = os.path.dirname(os.path.abspath(__file__))

env_path = os.path.join(current_dir, '../../.env')
# 載入 .env 裡的 API Key
load_dotenv(dotenv_path=env_path)

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def _format_locations_block():
    return "\n".join(
        [f"- {loc['location_id']}: {loc['zh_name']} / {loc['location_name']}" for loc in OPERABLE_LOCATIONS]
    )


def _format_objects_block():
    return "\n".join(
        [f"- {obj['zh_name']} / {obj['object_name']} (default: {obj['location_name']}, id {obj['location_id']})" for obj in OBJECT_CATALOG]
    )


HIGH_LEVEL_SYSTEM_PROMPT = f"""
You are a High-Level Task Planner for a smart service robot.
Your job is to parse a natural language command into structured high-level tasks.

The output will later be used by a low-level planner. Therefore, task boundaries must preserve
the correct physical object flow and final object locations.

==============================================================
SECTION 1 — TASK BOUNDARY RULES
==============================================================

RULE 1 — ONE PHYSICAL OBJECT, ONE TASK:
Every operation on the same physical object must stay inside the same high-level task.

RULE 2 — SPLIT ONLY WHEN OBJECTS ARE INDEPENDENT:
Only split tasks when they share no physical object interaction.

RULE 3 — DEPENDENCIES MUST BE VISIBLE IN DESCRIPTION:
If one step depends on another, say so explicitly in the task description.

RULE 4 — DESCRIBE THE FULL FLOW:
Each description must cover initial location, intermediate movements, and final location.

RULE 5 — `involved_items` MUST LIST STARTING LOCATIONS:
Use each object's initial location, not its future location.
Special tokens allowed: `pour_at`, `destination`, `return_to`, `User`.

RULE 6 - OBSERVATION-GATED TASKS MUST STAY AS ONE GATE TASK:
If the command includes "先看/先掃描/確認後再做" style logic (for example: if found do A, else do B),
you MUST output exactly ONE high-level gate task first, instead of expanding both branches now.
That gate task must:
- Keep the scan/check action and decision policy in the same task description.
- Include this exact runtime marker text in `description`: `先掃描，掃描後逐項插入後續任務`.
- Describe both branches explicitly in the same description using natural language:
    "若看到 X，執行 ...；若沒看到 X，執行 ...".
- Preserve final common goals (for example return object to fridge) in that same description.
- Keep `involved_items` focused on the scan location and known initial object locations only.

==============================================================
SECTION 2 — CANONICAL LOCATIONS
==============================================================

Use only these locations. Output the English location names below.

{_format_locations_block()}

==============================================================
SECTION 3 — CANONICAL OBJECTS
==============================================================

Use only the English object names below. Normalize Chinese input into these English names.

{_format_objects_block()}

Examples of normalization:
- 果汁 -> juice
- 可樂 -> cola
- 水杯 -> water_cup
- 飲料杯 -> drink_cup
- 礦泉水 -> mineral_water
- 衛生紙 -> tissue_box
- 濕紙巾 -> wet_wipe
- 遙控器 -> remote_control
- 藥罐 -> medicine_jar
- 剪刀 -> scissors
- 菜瓜布 -> scrub_sponge
- 洗手乳 -> hand_soap
- 鹽巴罐 -> salt_shaker
- 沖泡粉包 -> instant_powder_packet
- 鑰匙串 -> keyring
- 梳子 -> comb
- 相機 -> camera
- 耳機 -> headphones
- 碗 -> bowl

Do not invent new object names or new locations.

==============================================================
SECTION 4 — OUTPUT FORMAT
==============================================================

Output a strictly valid JSON object with a `tasks` array.
Each task must contain:
- `id` (integer)
- `name` (string)
- `description` (string)
- `involved_items` (array)
- `time_constraints` (object)
- `urgency_level` (string: `super_urgent` / `priority` / `normal`)
- `urgency_score` (integer: 10 / 3 / 0)

For `involved_items`:
- `item_name` must use lowercase English object names from the catalog.
- For special tokens, use exactly: `pour_at`, `destination`, `return_to`, `User`.
- `location` must be one of the canonical English location names above.
- `location_id` must match the location table.

==============================================================
SECTION 5 — URGENCY SCORING RULES
==============================================================

Assign urgency for each task using the original user request text:
- Level 1 `super_urgent` with score `10`:
  Trigger when the input includes words like `馬上`, `立刻`, `right now`, `immediately`.
- Level 2 `priority` with score `3`:
  Trigger when the input includes words like `可以優先`, `等等先幫我`, `先幫我`.
- Level 3 `normal` with score `0`:
  Any task that does not match Level 1 or Level 2.

If multiple urgency cues appear, always use the highest level.

==============================================================
SECTION 6 — DECISION GUIDELINES
==============================================================

- Keep all steps involving the same physical object in one task.
- If an item must be poured, returned, delivered, stored, or handed over, keep those steps in the same task.
- If a task has a `destination`, the destination must appear in `involved_items`.
- If a task has a return location, the `return_to` entry must appear in `involved_items`.
- If a task involves two independent object groups, they may be separated into two tasks.
- For observation-gated commands, do NOT pre-split into "found" and "not found" separate tasks.
- For observation-gated commands, do NOT emit multiple parallel alternatives as separate tasks.

Return only the JSON object. No markdown.
"""

def get_llm_task_plan(user_input):
    
    # user_input is a string containing the user's command
    print(f"{Fore.CYAN}李祖聖萬歲[High-Level] analyzing: {user_input}...{Style.RESET_ALL}")

    try:
        response = client.chat.completions.create(
            model="gpt-4o",  
            messages=[
                {"role": "system", "content": HIGH_LEVEL_SYSTEM_PROMPT},
                {"role": "user", "content": user_input}
            ],
            temperature=0.1,  
            response_format={"type": "json_object"} 
        )

        content = response.choices[0].message.content
        
        # 解析 JSON
        task_data = json.loads(content)
        return task_data

    except Exception as e:
        print(f"{Fore.RED}[Error] High-Level parsing failed: {e}{Style.RESET_ALL}")
        return None