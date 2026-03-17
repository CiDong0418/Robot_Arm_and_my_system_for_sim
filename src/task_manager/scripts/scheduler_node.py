#!/usr/bin/env python3
import rospy
import json
import time
from std_msgs.msg import String
from colorama import Fore, Style, init

init()

class SchedulerNode:
    def __init__(self):
        rospy.init_node('scheduler_node', anonymous=True)
        
        # 訂閱：來自 LLM Processor 的小任務
        self.sub = rospy.Subscriber('/subtasks_queue', String, self.callback)
        
        # (預留) 發布：給機器人控制器的指令
        # self.robot_pub = rospy.Publisher('/robot_execution', String, queue_size=10)
        
        print(f"{Fore.MAGENTA}[Scheduler] DABC Optimization Node Ready...{Style.RESET_ALL}")

    def callback(self, msg):
        try:
            # 1. 解碼 JSON
            subtasks = json.loads(msg.data)
            
            print(f"\n{Fore.CYAN}>>> [Scheduler] Received New Task Batch!{Style.RESET_ALL}")
            
            # 2. 模擬 DABC 最佳化 (這是您未來要放演算法的地方)
            optimized_schedule = self.run_dabc_optimization(subtasks)
            
            # 3. 輸出結果
            self.print_schedule(optimized_schedule)

        except json.JSONDecodeError:
            rospy.logerr("JSON 解碼失敗")

    def run_dabc_optimization(self, tasks):
        """ 模擬 DABC 運算過程 """
        print(f"{Fore.YELLOW}    [DABC] Calculating cost and constraints...{Style.RESET_ALL}")
        time.sleep(1.0) # 假裝算了一秒鐘
        # 未來這裡會呼叫您的 DABC Class
        return tasks 

    def print_schedule(self, tasks):
        print(f"{Fore.GREEN}✔ [Execution Plan Optimized]:{Style.RESET_ALL}")
        print("-" * 50)
        for t in tasks:
            # 讀取欄位 (相容您的 subtask_parser 輸出)
            gid = t.get('global_id', 'N/A')
            action = t.get('action_type', 'Action')
            params = t.get('parameters', '')
            duration = t.get('estimated_duration', 0)
            
            print(f"   [{gid}] {action:<25} | {params} ({duration}s)")
        print("-" * 50)

if __name__ == '__main__':
    node = SchedulerNode()
    rospy.spin()