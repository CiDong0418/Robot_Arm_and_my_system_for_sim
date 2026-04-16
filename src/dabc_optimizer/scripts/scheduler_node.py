#!/usr/bin/env python3
import rospy
import sys
import os
import json
from std_msgs.msg import String
from std_srvs.srv import Trigger, TriggerResponse
from datetime import datetime


# 123

# 把 src 資料夾強制加進 Python 的搜尋路徑 
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

# Import 我們剛寫好的 src 模組
from dabc_optimizer.dabc import DABC
from dabc_optimizer.first_llm_bee import get_llm_initial_schedule
from dabc_optimizer.fitness import TaskScheduler


class SchedulerNode:
    def __init__(self):
        rospy.init_node('dabc_scheduler_node')
        
        # 1. 任務緩衝區 (Buffer)
        self.task_buffer = []      # 存原始 JSON 物件
        self.task_lookup = {}      # 轉成 Dict 方便查找 {id: data}
        
        # 2. 訂閱小任務
        rospy.Subscriber("/subtasks_queue", String, self.task_callback)
        
        # 3. 發布排程結果
        self.result_pub = rospy.Publisher("/optimized_schedule", String, queue_size=10)
        
        # 4. 觸發服務 (Service) - 當你想排程時，呼叫這個
        rospy.Service('start_scheduling', Trigger, self.trigger_callback)

        self._log_all = []
        self._log_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), '../../task_manager/scheduler_log.json')
        )
        self._init_log()
        
        rospy.loginfo("[Scheduler] Ready. Collecting tasks... Call 'start_scheduling' to optimize.")
        rospy.loginfo(f"📝 排程 log 將儲存至: {self._log_path}")

    def _init_log(self):
        """每次節點啟動時清空排程 log 檔"""
        try:
            with open(self._log_path, 'w', encoding='utf-8') as f:
                json.dump([], f, ensure_ascii=False, indent=2)
        except Exception as error:
            rospy.logwarn(f"[Scheduler] 排程 log 初始化失敗: {error}")

    def _save_to_log(self, tasks):
        """把本次排程結果追加寫入 log 檔"""
        self._log_all.append({
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "schedule": tasks,
        })
        try:
            with open(self._log_path, 'w', encoding='utf-8') as f:
                json.dump(self._log_all, f, ensure_ascii=False, indent=2)
        except Exception as error:
            rospy.logwarn(f"[Scheduler] 排程 log 寫入失敗: {error}")

    @staticmethod
    def normalize_task_fields(task):
        normalized = dict(task)

        object_name = normalized.get('object') or normalized.get('target_object')
        if object_name:
            normalized.setdefault('object', object_name)
            normalized.setdefault('target_object', object_name)

        hand_name = normalized.get('hand') or normalized.get('hand_used')
        if hand_name:
            normalized.setdefault('hand', hand_name)
            normalized.setdefault('hand_used', hand_name)

        return normalized

    def task_callback(self, msg):
        """接收不斷進來的任務並累積
        這一個部份就是只要接到topic上面的小任務就會先存在buffer裡面
        id有進行修改過是全域id
        
        """
        try:
            new_tasks = json.loads(msg.data)
            # 將新任務加入 buffer
            for task in new_tasks:
                task = self.normalize_task_fields(task)
                # 為了防止重複 ID，這邊可以做個檢查，這裡先假設 ID 唯一
                self.task_buffer.append(task)
                
                # 建立 Lookup Table 供演算法使用
                t_id = task['global_id']  # 使用全域唯一 ID，避免多個大任務時 ID 衝突
                parent_id = task.get('parent_id')
                # 找出原本的dependency是什麼，然後轉成全域id的格式
                original_deps = task.get('dependencies', [])
                # dependencies 可能已由 subtask_parser 轉為全域 ID ("1_2")，也可能還是本地 step id (1)
                global_deps = []
                for d in original_deps:
                    if isinstance(d, str) and '_' in d:
                        global_deps.append(d)
                    else:
                        try:
                            di = int(d)
                            if parent_id is not None:
                                global_deps.append(f"{parent_id}_{di}")
                            else:
                                global_deps.append(str(d))
                        except Exception:
                            global_deps.append(str(d))
                
                task_payload = dict(task)
                task_payload.update({
                    'estimated_duration': task.get('estimated_duration', 10),
                    'hand_used': task.get('hand_used', None),
                    'dependencies': global_deps,
                    'action_type': task.get('action_type', 'PICK'),
                    'location_id': task.get('location_id', 1),  # 執行此動作的地點ID (1-12)，預設為 1
                    'target_object': task.get('target_object', task.get('object')),
                    'global_id': t_id,
                    'parent_id': parent_id,
                    'description': task.get('description', '')
                })
                self.task_lookup[t_id] = task_payload
                
            rospy.loginfo(f"[Scheduler] Received batch. Total tasks in buffer: {len(self.task_buffer)}")
            
        except Exception as e:
            rospy.logerr(f"JSON Parse Error: {e}")

    def trigger_callback(self, req):
        """當使用者呼叫 Service 時觸發 DABC
        在這個步驟，我們也要先去問 TaskExecutionNode 有沒有「還沒執行的舊任務」，
        拿回來跟 self.task_buffer 混在一起排。
        """
        # 在開始排程前，向 TaskExecutionNode 索取還沒執行的舊任務
        try:
            # 嘗試等待 1.0 秒看 service 在不在，如果在就去拿回來
            rospy.wait_for_service('/get_unexecuted_tasks', timeout=1.0)
            get_unexecuted = rospy.ServiceProxy('/get_unexecuted_tasks', Trigger)
            resp = get_unexecuted()
            if resp.success and resp.message:
                old_tasks = json.loads(resp.message)
                if old_tasks:
                    rospy.loginfo(f"[Scheduler] 🔄 Pulled {len(old_tasks)} unexecuted tasks from execution queue.")
                    # 將舊任務加進 buffer 及 lookup，準備跟新任務混和排程
                    for task in old_tasks:
                        task = self.normalize_task_fields(task)
                        self.task_buffer.append(task)
                        
                        t_id = task['global_id']
                        # 已經在 execution queue 的 task，其 dependencies 應該已經轉好全域 ID 了，直接取用
                        task_payload = dict(task)
                        task_payload.update({
                            'estimated_duration': task.get('estimated_duration', 10),
                            'hand_used': task.get('hand_used', None),
                            'dependencies': task.get('dependencies', []),
                            'action_type': task.get('action_type', 'PICK'),
                            'location_id': task.get('location_id', 1),
                            'target_object': task.get('target_object', task.get('object')),
                            'global_id': t_id,
                            'parent_id': task.get('parent_id'),
                            'description': task.get('description', '')
                        })
                        self.task_lookup[t_id] = task_payload
        except Exception as e:
            # 如果 node 還沒啟動或是找不到 service，就當作沒有舊任務
            pass

        if not self.task_buffer:
            return TriggerResponse(success=False, message="No tasks in buffer!")

        rospy.loginfo("--- Starting DABC Optimization ---")

        rospy.loginfo(f"目前準備排程的字典內容:\n{json.dumps(self.task_lookup, indent=2)}")

        rospy.loginfo("llm first bee")
        llm_initial_sequence = get_llm_initial_schedule(self.task_lookup)

        rospy.loginfo(f"LLM Initial Sequence: {llm_initial_sequence}")

        # if llm can not be use
        if not llm_initial_sequence:
            rospy.logwarn("LLM failed to provide an initial sequence. Proceeding with DABC without LLM guidance.")
            llm_initial_sequence = [task['global_id'] for task in self.task_buffer]
        


        # 1. 初始化 DABC
        optimizer = DABC(self.task_lookup, population_size=10, max_iterations=50, initial_seq=llm_initial_sequence)
        
        # 2. 執行運算
        best_seq, best_time = optimizer.optimize() # 開始進行abc演算法的計算，回傳的是最佳順序跟時間
        
        # 3. 處理結果
        if best_time == float('inf'):# 檢查是否找到有效解
            msg = "Optimization Failed: Could not find valid dependency order."
            rospy.logwarn(msg)
            return TriggerResponse(success=False, message=msg)
            
        # 4. 根據最佳順序進行手臂配置與托盤插單
        planner = TaskScheduler(self.task_lookup)
        optimized_tasks, plan_makespan = planner.build_execution_plan(best_seq)

        if plan_makespan == float('inf'):
            msg = "Optimization Failed: No feasible plan after tray insertion."
            rospy.logwarn(msg)
            return TriggerResponse(success=False, message=msg)

        # 5. 發布結果
        json_output = json.dumps(optimized_tasks)
        self.result_pub.publish(json_output)
        self._save_to_log(optimized_tasks)
        
        result_msg = f"Optimization Done! Makespan: {best_time}s. Sequence: {best_seq}"
        rospy.loginfo(result_msg)
        
        # 清空 buffer 準備下一輪任務
        self.task_buffer = []
        self.task_lookup = {}
        
        return TriggerResponse(success=True, message=result_msg)

if __name__ == '__main__':
    try:
        SchedulerNode()
        rospy.spin()
    except rospy.ROSInterruptException:
        pass