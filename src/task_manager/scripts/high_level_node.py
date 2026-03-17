#!/usr/bin/env python3
import rospy
import sys
import os
import json
from std_msgs.msg import String

# 設定路徑以匯入 modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))
from task_module.llm_parser import get_llm_task_plan

# 高階任務解析節點
# 功能說明:
# 這個節點負責接收使用者的文字指令，呼叫 LLM 進行高階任務解析，
# 並將解析後的多個大任務逐一發布到 /high_level_stream 話題上。

# 訂閱話題: /user_command (String)
# 發布話題: /high_level_stream (String, JSON 格式)

class HighLevelNode:
    def __init__(self):
        rospy.init_node('high_level_node', anonymous=True)
        

        # 避免ID重複
        self.task_id_counter = 1

        # 訂閱：使用者指令
        self.sub = rospy.Subscriber('/user_command', String, self.user_command_callback) # 這裡的self.sub很重要，確保訂閱者存活
        
        # 發布：單個大任務 (給 subtask_node)
        self.pub = rospy.Publisher('/high_level_stream', String, queue_size=20)
        
        rospy.loginfo("=== [Node 2] High-Level Parser Ready ===")

    def user_command_callback(self, msg):
        user_input = msg.data
        rospy.loginfo(f"收到指令: {user_input}")

        # 1. 呼叫 LLM 取得 JSON
        plan_data = get_llm_task_plan(user_input) # 呼叫您原本的 llm_parser.py，可以有多個大任務
        
        if plan_data and "tasks" in plan_data:
            task_list = plan_data["tasks"]
            rospy.loginfo(f"解析成功！共 {len(task_list)} 個大任務。")
            
            # 2. 像流水線一樣，一個一個發送出去
            for task in task_list:
                # 分配唯一 ID
                task['id'] = self.task_id_counter
                self.task_id_counter += 1


                # 為了讓下一個節點容易處理，我們轉成 JSON 字串發送
                json_str = json.dumps(task, ensure_ascii=False)
                
                self.pub.publish(json_str) # 發送單個大任務
                rospy.loginfo(f"--> [Stream] 發送大任務 ID {task['id']}: {task['name']}")
                
        else:
            rospy.logwarn("意圖解析失敗，或者 LLM 沒有回傳 tasks 欄位。")

if __name__ == '__main__':
    node = HighLevelNode()
    rospy.spin()