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

class TaskScheduler:
    def __init__(self, task_lookup):
        """
        :param task_lookup: 字典格式 {id: {duration, hand, deps, action_type, location_id, ...}}
        """
        self.tasks = task_lookup

    def calculate_makespan(self, sequence):
        """
        計算 Makespan，同時考慮：
        1. 依賴關係 (Dependency)
        2. 手臂容量狀態 (Hand Capacity) - 避免滿手時還去抓東西
        3. 隱性移動成本 (Implicit Travel Cost) - 根據前後任務的 location_id 自動計算移動時間
        """
        
        # --- 1. 初始化狀態 ---
        resource_clock = {
            "Left_Arm": 0,
            "Right_Arm": 0,
            "Base": 0
        }
        
        # 手臂狀態模擬 (None 代表空手)
        hand_holding = {
            "Left_Arm": None,
            "Right_Arm": None
        }
        
        # 機器人當前位置 (初始位置設為 1，Living Room Table 1)
        current_location_id = 1
        
        task_finish_times = {}
        
        # --- 2. 開始模擬排程 ---
        for task_id in sequence:
            task = self.tasks[task_id]
            hand = task['hand_used']
            action = task['action_type']
            task_location_id = task.get('location_id', current_location_id)  # 取得此任務的執行位置
            
            # === 檢查 A: 依賴關係 (Dependency Check) ===
            start_time_by_deps = 0
            for dep_id in task['dependencies']:
                if dep_id not in task_finish_times:
                    return float('inf')  # 違反依賴順序，直接判死刑
                start_time_by_deps = max(start_time_by_deps, task_finish_times[dep_id])
            
            # === 檢查 B: 手臂容量與邏輯 (Hand State Check) ===
            if hand in ["Left_Arm", "Right_Arm"]:
                current_holding = hand_holding[hand]
                
                if action == "PICK":
                    if current_holding is not None:
                        return float('inf')  # 手已滿還想抓
                    hand_holding[hand] = "HOLDING_SOMETHING"
                    
                elif action == "PLACE":
                    if current_holding is None:
                        return float('inf')  # 空手沒東西可放
                    hand_holding[hand] = None

                elif action == "STORE_ON_TRAY":
                    # 把手上的東西放到胸前托盤 → 手變空
                    if current_holding is None:
                        return float('inf')  # 空手無法放到托盤
                    hand_holding[hand] = None

                elif action == "RETRIEVE_FROM_TRAY":
                    # 從托盤取出物品 → 手要先是空的
                    if current_holding is not None:
                        return float('inf')  # 手已滿無法從托盤取物
                    hand_holding[hand] = "HOLDING_SOMETHING"

                elif action == "POUR":
                    # POUR 不改變持有狀態：傾倒後手上仍持有來源瓶子
                    if current_holding is None:
                        return float('inf')  # 空手無法倒東西
                    # hand_holding 不變（還拿著瓶子）

            # === C. 計算隱性移動時間 (Implicit Travel Cost) ===
            travel_time = _topo.get_travel_time(current_location_id, task_location_id)
            
            # 更新機器人當前位置
            current_location_id = task_location_id

            # === D. 計算總時間 ===
            # duration 優先使用固定時間表，確保排程結果可重複
            # 若動作類型不在表中才 fallback 到 LLM 給的 estimated_duration
            duration = ACTION_DURATION.get(action, task.get('estimated_duration', DEFAULT_ACTION_DURATION))
            
            if hand == "Left_Arm":
                earliest_start = max(start_time_by_deps, resource_clock["Left_Arm"])
                # Base 也需要移動過去，所以也要等 Base 空閒
                earliest_start = max(earliest_start, resource_clock["Base"])
                start_time = earliest_start + travel_time
                end_time = start_time + duration
                resource_clock["Left_Arm"] = end_time
                resource_clock["Base"] = start_time  # Base 抵達後就空閒了
                
            elif hand == "Right_Arm":
                earliest_start = max(start_time_by_deps, resource_clock["Right_Arm"])
                earliest_start = max(earliest_start, resource_clock["Base"])
                start_time = earliest_start + travel_time
                end_time = start_time + duration
                resource_clock["Right_Arm"] = end_time
                resource_clock["Base"] = start_time
                
            else:
                # 共用資源 (Base) 或 雙手同時動作
                earliest_start = max(start_time_by_deps, resource_clock["Base"])
                start_time = earliest_start + travel_time
                end_time = start_time + duration
                resource_clock["Base"] = end_time

            task_finish_times[task_id] = end_time

        makespan = max(task_finish_times.values()) if task_finish_times else 0
        return makespan