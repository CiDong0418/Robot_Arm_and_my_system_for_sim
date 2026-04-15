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

For `involved_items`:
- `item_name` must use lowercase English object names from the catalog.
- For special tokens, use exactly: `pour_at`, `destination`, `return_to`, `User`.
- `location` must be one of the canonical English location names above.
- `location_id` must match the location table.

==============================================================
SECTION 5 — DECISION GUIDELINES
==============================================================

- Keep all steps involving the same physical object in one task.
- If an item must be poured, returned, delivered, stored, or handed over, keep those steps in the same task.
- If a task has a `destination`, the destination must appear in `involved_items`.
- If a task has a return location, the `return_to` entry must appear in `involved_items`.
- If a task involves two independent object groups, they may be separated into two tasks.

Return only the JSON object. No markdown.
"""
      "description": "Step 1: Pick up Medicine Bottle from Room A Desk (location_id 10). Step 2: Carry the Medicine Bottle to Living Room Sofa 1 (location_id 3) and hand it over to the User. Step 3: After handover, wait for user to take medicine. Step 4: Pick up the (now empty) Medicine Bottle from the user at Living Room Sofa 1. Step 5: Bring the empty Medicine Bottle to Kitchen Table 2 (location_id 8). Note: Step 4 depends on Step 3 (handover must complete first); Step 5 depends on Step 4.",
      "involved_items": [
        {"item_name": "Medicine Bottle", "location": "Room A Desk",        "location_id": 10},
        {"item_name": "User",            "location": "Living Room Sofa 1", "location_id": 3},
        {"item_name": "destination",     "location": "Kitchen Table 2",    "location_id": 8}
      ],
      "time_constraints": {"start_after": null, "finish_before": null}
    }
  ]
}

--- EXAMPLE D: Multiple objects, some shared interactions ---

Input:
"Make coffee: get the coffee powder from Kitchen Table 1 and the mug from Kitchen Table 2.
 Mix coffee in the mug at Kitchen Table 1.
 Bring the mug to Room B Desk.
 Put the coffee powder back on Kitchen Table 1."

Analysis:
  - Coffee powder and mug are BOTH used in the mixing step → they share an interaction → ONE task.

✅ CORRECT Output:
{
  "tasks": [
    {
      "id": 1,
      "name": "Prepare Coffee and Deliver to Room B",
      "description": "Step 1: Pick up Coffee Powder from Kitchen Table 1 (location_id 7). Step 2: Pick up Mug from Kitchen Table 2 (location_id 8). Step 3: Mix coffee powder into the mug at Kitchen Table 1 (location_id 7) — depends on Step 1 and Step 2. After mixing, Coffee Powder is at Kitchen Table 1 and Mug now contains coffee. Step 4: Deliver the Mug (with coffee) to Room B Desk (location_id 12) — depends on Step 3. Step 5: Return Coffee Powder to Kitchen Table 1 (location_id 7) — depends on Step 3 (mixing must be complete; powder is already at Kitchen Table 1 so this is a confirmation step).",
      "involved_items": [
        {"item_name": "Coffee Powder", "location": "Kitchen Table 1",  "location_id": 7},
        {"item_name": "Mug",           "location": "Kitchen Table 2",  "location_id": 8},
        {"item_name": "pour_at",       "location": "Kitchen Table 1",  "location_id": 7},
        {"item_name": "destination",   "location": "Room B Desk",      "location_id": 12},
        {"item_name": "return_to",     "location": "Kitchen Table 1",  "location_id": 7}
      ],
      "time_constraints": {"start_after": null, "finish_before": null}
    }
  ]
}

==============================================================
SECTION 5 — QUICK CHECKLIST BEFORE OUTPUTTING
==============================================================

Before writing your final JSON output, verify:
[ ] Does any single physical object appear in MORE THAN ONE task? → If yes, MERGE those tasks.
[ ] Does every task's `description` include the FULL step-by-step flow?
[ ] Does every step in `description` that depends on a previous step say "depends on Step X"?
[ ] Does `involved_items` include ALL objects the robot will physically touch?
[ ] Are ALL `location` values from the 12 allowed locations? No invented names?
[ ] Are ALL `location_id` values the correct integers (1-12)?
[ ] For POUR/MIX tasks: is there a `pour_at` entry in `involved_items`?
[ ] For DELIVERY tasks: is there a `destination` entry in `involved_items`?
[ ] For RETURN tasks: is there a `return_to` entry in `involved_items`?
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