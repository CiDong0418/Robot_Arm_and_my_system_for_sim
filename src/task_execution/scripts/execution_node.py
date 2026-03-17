#!/usr/bin/env python3
import rospy
import json
import collections
from std_msgs.msg import String, Int32
from std_srvs.srv import Trigger, TriggerResponse

class TaskExecutionNode:
    def __init__(self):
        rospy.init_node('task_execution_node')
        
        # 任務佇列 (Queue)，使用 deque 實作以便左邊彈出
        self.task_queue = collections.deque()
        
        # 機器人狀態: 0 (閒置), 1 (執行中)
        self.robot_status = 0
        
        # 訂閱 /optimized_schedule (接收 DABC 排好的任務列表)
        rospy.Subscriber("/optimized_schedule", String, self.schedule_callback)
        
        # 訂閱 /robot_status (接收機器人閒置或忙碌的狀態)
        rospy.Subscriber("/robot_status", Int32, self.status_callback)
        
        # 發布 /current_task (發送單一任務給機器人執行)
        self.action_pub = rospy.Publisher("/current_task", String, queue_size=10)
        
        # 提供 Service, 供 DABC 重排時呼叫, 拿回還沒執行的舊任務並清空本機佇列
        rospy.Service('get_unexecuted_tasks', Trigger, self.get_unexecuted_tasks_callback)
        
        rospy.loginfo("[TaskExecution] Ready. Waiting for optimized schedule and robot status...")
        
        # 定期檢查是否可以派發任務給機器人
        self.timer = rospy.Timer(rospy.Duration(0.5), self.try_dispatch)
        
    def schedule_callback(self, msg):
        try:
            tasks = json.loads(msg.data)
            # 這裡接收到的是「包含未執行舊任務 + 新增任務」的全新 DABC 排程結果
            self.task_queue = collections.deque(tasks)
            rospy.loginfo(f"[TaskExecution] 📥 Received optimized schedule with {len(self.task_queue)} tasks.")
        except Exception as e:
            rospy.logerr(f"[TaskExecution] JSON Parse Error: {e}")
            
    def status_callback(self, msg):
        # 只要機器人回傳 0，就代表閒置了
        if msg.data == 0 and self.robot_status == 1:
            rospy.loginfo("[TaskExecution] 🟢 Robot finished previous task. Status changed to IDLE (0).")
        self.robot_status = msg.data
        
    def get_unexecuted_tasks_callback(self, req):
        """當 DABC 需要重新排程時，他會來呼叫這個 Service 取回 queue 裡面還沒做的任務"""
        unexecuted = list(self.task_queue)
        
        # 把尚未執行的任務轉成字串
        tasks_json = json.dumps(unexecuted)
        
        # 立即清空佇列，等待 DABC 混和新舊任務後排出來的最佳版本
        self.task_queue.clear()
        
        rospy.loginfo(f"[TaskExecution] 🔄 DABC requested unexecuted tasks. Extracted {len(unexecuted)} tasks.")
        return TriggerResponse(success=True, message=tasks_json)
        
    def try_dispatch(self, event=None):
        # 只要機器人目前狀態為 0 (閒置) 且佇列裡還有任務，就拿第一筆去派發
        if self.robot_status == 0 and self.task_queue:
            next_task = self.task_queue.popleft()
            
            # 馬上將本機紀錄的狀態鎖定為 1 (執行中)，防止 0.5 秒後 timer 又重複派發
            # 直到機器人接收並執行完畢後對 /robot_status 再次發出 0 解鎖為止
            self.robot_status = 1
            
            task_json = json.dumps(next_task, ensure_ascii=False)
            self.action_pub.publish(task_json)
            rospy.loginfo(f"[TaskExecution] 🚀 Dispatched Task to Robot: {next_task.get('global_id')} ({next_task.get('action_type')} @ Loc {next_task.get('location_id')})")

if __name__ == '__main__':
    try:
        TaskExecutionNode()
        rospy.spin()
    except rospy.ROSInterruptException:
        pass
