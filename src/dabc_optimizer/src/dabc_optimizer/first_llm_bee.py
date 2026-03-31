import os
import json
from openai import OpenAI
from dotenv import load_dotenv
from colorama import Fore, Style

# 設定路徑並載入 .env
current_dir = os.path.dirname(os.path.abspath(__file__))
candidate_env_paths = [
    os.path.abspath(os.path.join(current_dir, "..", "..", ".env")),
    os.path.abspath(os.path.join(current_dir, ".env")),
]

for env_path in candidate_env_paths:
    if os.path.isfile(env_path):
        load_dotenv(dotenv_path=env_path)
        break

api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise RuntimeError(
        "找不到 OPENAI_API_KEY。請確認 .env 位於 dabc_optimizer/.env，或先 export OPENAI_API_KEY。"
    )

client = OpenAI(api_key=api_key)

# === 第一隻蜜蜂 (LLM 全域排程) 專用的 System Prompt ===
GLOBAL_SCHEDULE_SYSTEM_PROMPT = """
You are an expert Robot Task Scheduler for a dual-arm robot.
You will receive a JSON dictionary containing all parsed atomic tasks.
Each task is represented by a Key (Task ID) and a Value (Task Details).

Task Details include:
- `action_type`: The specific robot action (e.g., "PICK", "PLACE", "OPEN_DRAWER", "STORE_ON_TRAY").
- `dependencies`: List of Task IDs that MUST be executed BEFORE this task.
- `hand_used`: "Left_Arm", "Right_Arm", or null.
- `estimated_duration`: Execution time in seconds.

Your objective is to generate a SINGLE, flat list of Task IDs representing the optimal execution sequence.

**CRITICAL RULES (READ CAREFULLY):**
1. **Strict Dependency:** A task MUST appear in the sequence AFTER all of its dependencies.
2. **Completeness:** ALL Task IDs from the input dictionary MUST be included in the sequence exactly once.
3. **Hand Capacity Limit:** Each arm can only hold one item at a time. The actions "PICK" and "RETRIEVE_FROM_TRAY" OCCUPY the hand. If an arm is holding something, it cannot do another "PICK" or "RETRIEVE_FROM_TRAY" until a "PLACE" or "STORE_ON_TRAY" frees the hand.
4. **Dynamic Hand Assignment:** Many tasks will have `hand_used = null`. You MUST still produce a valid order, but you should NOT add or remove tasks. A downstream scheduler will assign a valid hand and may insert helper actions (STORE_ON_TRAY, RETRIEVE_FROM_TRAY, HANDOVER) when needed.
5. **Scissors Rule (Important):** Tasks involving `scissors` can ONLY be performed by Right_Arm. If Right_Arm is already holding something and a scissors task is next, the downstream scheduler will insert a HANDOVER from Right_Arm to Left_Arm first. Your job is to order tasks so this can happen without breaking dependencies.
6. **Open Drawer Rule (Important):** `OPEN_DRAWER` can ONLY use Left_Arm and the left hand must be empty. If Left_Arm is holding something, the scheduler will insert STORE_ON_TRAY first. Avoid ordering that would make this impossible.
7. **Tray Rule (Important):** When both hands are full and another PICK is required, the downstream scheduler will insert STORE_ON_TRAY to free a hand. Do NOT add this yourself; just avoid ordering that would force impossible dependency violations.
8. **Cross-Task Interleaving:** You are encouraged to mix subtasks from different high-level goals (different Task ID prefixes) to minimize makespan, as long as you respect dependencies and hand capacity limits.

**Examples:**
Input task IDs: ["1_1"=PICK(cup), "1_2"=PICK(cola), "1_3"=PICK(scissors), "1_4"=PLACE(cup), "1_5"=PLACE(cola), "1_6"=OPEN_DRAWER(scissors->drawer)]
Bad order (invalid): ["1_1", "1_2", "1_3", ...] because both hands are full and scissors must be Right_Arm; a HANDOVER will be needed before "1_3".
Good order (valid): ["1_1", "1_2", "1_4", "1_3", "1_6", "1_5"] (frees a hand before the scissors step and respects dependencies).

**Output Format:**
You must output a strictly valid JSON object like this:
{
    "initial_sequence": ["4_1", "5_1", "4_2", "5_2", ...]
}
"""

def get_llm_initial_schedule(task_lookup_dict):
    """
    接收 scheduler_node 整理好的 task_lookup 字典，
    請 LLM 考慮依賴關係與雙臂交錯，排定一個全域初始順序。
    """
    print(f"{Fore.MAGENTA}🐝 [First LLM Bee] Analyzing global sequence for {len(task_lookup_dict)} tasks...{Style.RESET_ALL}")
    
    # 將字典轉為字串餵給 LLM
    lookup_str = json.dumps(task_lookup_dict, ensure_ascii=False, indent=2)
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o",  
            messages=[
                {"role": "system", "content": GLOBAL_SCHEDULE_SYSTEM_PROMPT},
                {"role": "user", "content": f"Task Dictionary:\n{lookup_str}"}
            ],
            temperature=0.1,  # 保持極低溫度以確保邏輯穩定
            response_format={"type": "json_object"} 
        )

        content = response.choices[0].message.content
        result_data = json.loads(content)
        
        if "initial_sequence" in result_data:
            sequence = result_data["initial_sequence"]
            print(f"{Fore.GREEN}🐝 [First LLM Bee] Sequence successfully generated!{Style.RESET_ALL}")
            return sequence
        else:
            print(f"{Fore.RED}[Error] 'initial_sequence' key not found in LLM response.{Style.RESET_ALL}")
            return None

    except Exception as e:
        print(f"{Fore.RED}[Error] First LLM Bee generation failed: {e}{Style.RESET_ALL}")
        return None