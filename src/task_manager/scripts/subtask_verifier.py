#!/usr/bin/env python3
import rospy
import json
import os
import csv
import datetime
from std_msgs.msg import String

class SubtaskVerifier:
    def __init__(self):
        rospy.init_node('subtask_verifier', anonymous=True)
        
        self.topic_name = "/subtasks_queue"
        rospy.Subscriber(self.topic_name, String, self.callback)
        
        self.log_dir = os.path.expanduser("~/catkin_ws/logs/task_verification")
        if not os.path.exists(self.log_dir):
            os.makedirs(self.log_dir)
            
        rospy.loginfo(f"[{rospy.get_name()}] Ready. Waiting for tasks on {self.topic_name}...")

    def callback(self, msg):
        try:
            task_list = json.loads(msg.data)
            
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            filename = f"Task_Check_{timestamp}.csv"
            filepath = os.path.join(self.log_dir, filename)
            
            # --- 修改重點：加入 global_id 和 parent_id ---
            headers = [
                'global_id',        # 全域 ID (如 1_1)
                'parent_id',        # 主任務 ID
                'step_id',          # 步驟 ID
                'action_type', 
                'target_object', 
                'target_location', 
                'hand_used', 
                'dependencies', 
                'estimated_duration', 
                'description'
            ]
            # ----------------------------------------
            
            with open(filepath, 'w', newline='', encoding='utf-8-sig') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=headers)
                writer.writeheader()
                
                for task in task_list:
                    # 使用 get 確保就算欄位是空的也不會報錯
                    row_data = {k: task.get(k) for k in headers}
                    
                    # 處理 dependencies 格式 (List 轉 String)
                    if isinstance(row_data['dependencies'], list):
                        row_data['dependencies'] = str(row_data['dependencies'])
                    
                    writer.writerow(row_data)
                    
            rospy.loginfo(f"✅ CSV Generated with correct IDs: {filepath}")
            
        except Exception as e:
            rospy.logerr(f"Error: {e}")

if __name__ == '__main__':
    try:
        SubtaskVerifier()
        rospy.spin()
    except rospy.ROSInterruptException:
        pass