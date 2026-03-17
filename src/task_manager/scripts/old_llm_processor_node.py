#!/usr/bin/env python3
import rospy
import sys
import os
import json
from std_msgs.msg import String

# === 設定路徑以匯入 modules ===
# 這行讓 Python 找得到 ../src/task_module 資料夾
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

# 匯入您原本寫好的模組 (確保 __init__.py 存在)
from task_module.llm_parser import get_llm_task_plan
from task_module.subtask_parser import decompose_task

class LLMProcessorNode:
    def __init__(self):
        rospy.init_node('llm_processor_node', anonymous=True)
        
        # 訂閱：使用者指令（來自 main_input_node）
        self.sub = rospy.Subscriber('/user_command', String, self.callback) # 這裡的self.sub很重要，確保訂閱者存活
        
        # 發布：處理好的小任務 JSON (給排程器)
        self.pub = rospy.Publisher('/subtasks_queue', String, queue_size=10)
        
        rospy.loginfo("LLM Processor Ready (Waiting for commands...)")

    def callback(self, msg):
        user_input = msg.data
        rospy.loginfo(f"收到指令: {user_input}，開始解析...")

        # --- Stage 1: 大任務解析 (High-Level) ---
        # 呼叫您原本的 llm_parser.py
        high_level_plan = get_llm_task_plan(user_input)
        
        if high_level_plan and "tasks" in high_level_plan:
            rospy.loginfo(f"大任務解析成功，包含 {len(high_level_plan['tasks'])} 個任務")
            
            # --- Stage 2: 逐一拆解成小任務 (Low-Level) ---
            for task in high_level_plan["tasks"]:
                rospy.loginfo(f"正在拆解任務: {task['name']} ...")
                
                # 呼叫您原本的 subtask_parser.py
                subtasks = decompose_task(task)
                
                if subtasks:
                    # 打包成 JSON 字串
                    json_payload = json.dumps(subtasks, ensure_ascii=False)
                    
                    # 發送給下一個節點 (Scheduler)
                    self.pub.publish(json_payload)
                    rospy.loginfo(f"--> 已發送 {len(subtasks)} 個原子動作給 Scheduler")
                else:
                    rospy.logwarn(f"任務 {task['name']} 拆解失敗")
        else:
            rospy.logwarn("無法解析使用者意圖 (High-Level Parsing Failed)")

if __name__ == '__main__':
    node = LLMProcessorNode()
    rospy.spin()