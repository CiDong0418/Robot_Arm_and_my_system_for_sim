#!/usr/bin/env python3
import rospy
import sys
import os
import json
from std_msgs.msg import String
from datetime import datetime

# 訂閱話題: /high_level_stream (String, JSON 格式)
# 發布話題: /subtasks_queue (String, JSON 格式)

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))
from task_module.subtask_parser import decompose_task

# 儲存原子任務 log 的路徑
LOG_PATH = os.path.join(os.path.dirname(__file__), '../subtask_log.json')

class SubtaskNode:
    def __init__(self):
        rospy.init_node('subtask_node', anonymous=True)

        # 訂閱：大任務輸出 (來自 high_level_node)
        self.sub = rospy.Subscriber('/high_level_stream', String, self.subtask_callback)

        # 發布：拆解完的小任務序列 (準備給 Scheduler 排程器)
        self.pub = rospy.Publisher('/subtasks_queue', String, queue_size=10)

        # 每次節點啟動時清空 log，準備這次新的紀錄
        self._log_all = []
        self._init_log()

        rospy.loginfo("=== [Node 3] Sub-Task Decomposer Ready ===")
        rospy.loginfo(f"📝 原子任務 log 將儲存至: {LOG_PATH}")

    def _init_log(self):
        """每次節點啟動時清空 log 檔"""
        with open(LOG_PATH, 'w', encoding='utf-8') as f:
            json.dump([], f, ensure_ascii=False, indent=2)

    def _save_to_log(self, task_id, task_name, subtasks):
        """把這批原子任務追加寫入 log 檔"""
        self._log_all.append({
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "parent_task_id": task_id,
            "parent_task_name": task_name,
            "subtasks": subtasks
        })
        with open(LOG_PATH, 'w', encoding='utf-8') as f:
            json.dump(self._log_all, f, ensure_ascii=False, indent=2)

    def subtask_callback(self, msg):

        try:
            high_level_task = json.loads(msg.data)

            task_id = int(high_level_task.get('id', -1))  # 強制轉成整數
            task_name = high_level_task.get('name', 'Unknown')

            rospy.loginfo(f"📥 收到大任務 [{task_id}] {task_name}，開始細部拆解...")

            # call subtask_parser.py
            subtasks = decompose_task(high_level_task)

            if subtasks:
                # 儲存到 log 檔
                self._save_to_log(task_id, task_name, subtasks)

                # 轉成 JSON 發布
                result_json = json.dumps(subtasks, ensure_ascii=False)
                self.pub.publish(result_json)
                rospy.loginfo(f"📤 任務 [{task_id}] 拆解完成！已發送 {len(subtasks)} 個原子動作。")
                rospy.loginfo(f"💾 已儲存至 {LOG_PATH}")
            else:
                rospy.logwarn(f"⚠️ 任務 [{task_id}] 拆解失敗或回傳空值。")

        except json.JSONDecodeError:
            rospy.logerr("收到無效的 JSON 格式，無法解析。")
        except Exception as e:
            rospy.logerr(f"處理過程發生錯誤: {e}")

if __name__ == '__main__':
    node = SubtaskNode()
    rospy.spin()
