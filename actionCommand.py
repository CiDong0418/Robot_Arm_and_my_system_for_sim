#!/usr/bin/env python3
import rospy
from std_msgs.msg import String
import rospy
import json
import time
from geometry_msgs.msg import Point
import os
import threading
import math
robot_state = False
last_done_count = 0
new_done_count = 0
def wait_for_robot_action_completion():
    global robot_state
    # robot_state = False
    while not robot_state or last_done_count == new_done_count:
        time.sleep(0.5)
    robot_state = False

def action_state_callback(msg):
    global robot_state, new_done_count, last_done_count
    """接收並處理動作狀態"""
    state = msg.data
    rospy.loginfo(f"收到動作狀態: {state}")
    if state == "Done":
        rospy.loginfo("機器人動作完成，可以進行下一步操作。")
        robot_state = True 
        last_done_count = new_done_count
        new_done_count += 1


rospy.Subscriber('action_state', String, action_state_callback)




class PostureCommandPublisher:
    def __init__(self):
        
        self.pub = rospy.Publisher('posture_command', String, queue_size=10)
        rospy.sleep(1)

    def pos_synchronize_move(self,ox_deg, oy_deg, oz_deg, X, Y, Z, object_width):
        """同步移動命令"""
        command = {
            "action": "pos_synchronize_move",  
            "x": float(X),
            "y": float(Y),
            "z": float(Z),
            "ox_deg": float(ox_deg),
            "oy_deg": float(oy_deg),
            "oz_deg": float(oz_deg),
            "object_width": float(object_width)
        }
        self._send(command)
        wait_for_robot_action_completion()
    
    def pos_single_move(self, arm, ox_deg, oy_deg, oz_deg, X, Y, Z):
        """單一移動命令"""
        command = {
            "action": "pos_single_move",  
            "arm": arm,
            "x": float(X),
            "y": float(Y),
            "z": float(Z),
            "ox_deg": float(ox_deg),
            "oy_deg": float(oy_deg),
            "oz_deg": float(oz_deg)
        }
        self._send(command)
        wait_for_robot_action_completion()
    
    def pos_dual_move(self, lox_deg, loy_deg, loz_deg, lx, ly, lz, rox_deg, roy_deg, roz_deg, rx, ry, rz):
        """雙臂移動命令"""
        command = {
            "action": "pos_dual_move",  # 識別欄位
            "left": {
                "x": float(lx),
                "y": float(ly),
                "z": float(lz),
                "ox_deg": float(lox_deg),
                "oy_deg": float(loy_deg),
                "oz_deg": float(loz_deg)
            },
            "right": {
                "x": float(rx),
                "y": float(ry),
                "z": float(rz),
                "ox_deg": float(rox_deg),
                "oy_deg": float(roy_deg),
                "oz_deg": float(roz_deg)
            }
        }
        self._send(command)
        wait_for_robot_action_completion()
    def gripper_control(self, arm, angle=700):
        """關閉夾爪命令"""
        command = {
            "action": "gripper_control",  
            "arm": arm,
            "angle": angle
        }
        self._send(command)
        wait_for_robot_action_completion()
    def open_gripper(self, arm):
        """打開夾爪命令"""
        command = {
            "action": "open_gripper",  
            "arm": arm
        }
        self._send(command)
        wait_for_robot_action_completion()

    def close_gripper(self, arm):
        """關閉夾爪命令"""
        command = {
            "action": "gripper_control",  
            "arm": arm,
            "angle": 250
        }
        self._send(command)
        wait_for_robot_action_completion()
    def neck_control(self, yaw, pitch):
        """頸部控制命令"""
        command = {
            "action": "neck_control",  
            "yaw": float(yaw),
            "pitch": float(pitch)
        }
        self._send(command)
        wait_for_robot_action_completion()
    def _send(self, command):
        global robot_state
        """統一發送函式"""
        msg = String()
        msg.data = json.dumps(command)
        print("Sending: {}".format(command))
        
        robot_state = False
        self.pub.publish(msg)
        # rospy.sleep(0.1)
    def initial_position(self):
        self.pos_dual_move(-180.0, 35.0, 0.0,  420, 130, -130, 0.0, (180-35.0), 0.0,  420, -130, -130)
    def single_arm_initial_position(self, arm):
        if arm == "left":
            self.pos_single_move("left", -180.0, 35.0, 0.0,  420, 130, -130)
        elif arm == "right":
            self.pos_single_move("right", 0.0, (180-35.0), 0.0,  420, -130, -130)  

    def pick(self, arm, x, y, z, theta=35.0, gripper_length=23.3): 
        #theta(degree)：是夾爪與水平面的夾角，預設為35度，x,y,z是手臂世界座標系下的物體位置
        
        if arm == "left":
            sign = 1
            ox = -180.0
            oy = theta
            oz = 0.0
       
        elif arm == "right":
            sign = -1
            ox = 0.0
            oy = (180-theta)
            oz = 0.0
        
        
        distance = 100  # 先移動到距離物品多遠，以防碰撞, 可以根據實際情況調整
        # gripper_length = 23.3  # 夾爪延伸長度，東西越寬長度越小
        self.single_arm_initial_position(arm)
        while True:
            print(f"即將移動到: x={x - distance * math.sin(math.radians(theta))}, y={y + sign * distance * math.cos(math.radians(theta))}, z={z}")
            user_input = input("輸入 1 繼續下一步動作，或按 q 退出: ")
            if user_input == "1":
                print("✓ 繼續執行...")
            
                break 
            elif user_input.lower() == "q":
                print("✗ 取消動作")
                exit()
            else:
                print("⚠ 請輸入 1 或 q")
        self.pos_single_move(arm, ox, oy, oz, x - distance * math.sin(math.radians(theta)), y + sign * distance * math.cos(math.radians(theta)), z)
        while True:
            print(f"即將移動到：x={x - gripper_length * math.sin(math.radians(theta))}, y={y + sign * gripper_length * math.cos(math.radians(theta))}, z={z}")
            user_input = input("輸入 1 繼續下一步動作，或按 q 退出: ")
            if user_input == "1":
                print("✓ 繼續執行...")
            
                break 
            elif user_input.lower() == "q":
                print("✗ 取消動作")
                exit()
            else:
                print("⚠ 請輸入 1 或 q")
        
        self.pos_single_move(arm, ox, oy, oz, x - gripper_length * math.sin(math.radians(theta)), y + sign * gripper_length * math.cos(math.radians(theta)), z )
        # self.pos_single_move(arm, ox, oy, oz, x, y , z)
        while True:
            user_input = input("輸入 1 繼續下一步動作，或按 q 退出: ")
            if user_input == "1":
                print("✓ 繼續執行...")
            
                break 
            elif user_input.lower() == "q":
                print("✗ 取消動作")
                exit()
            else:
                print("⚠ 請輸入 1 或 q")
        self.close_gripper(arm)
        while True:
            user_input = input("輸入 1 繼續下一步動作，或按 q 退出: ")
            if user_input == "1":
                print("✓ 繼續執行...")
            
                break 
            elif user_input.lower() == "q":
                print("✗ 取消動作")
                exit()
            else:
                print("⚠ 請輸入 1 或 q")
        self.pos_single_move(arm, ox, oy, oz, x - gripper_length * math.sin(math.radians(theta)), y + sign * gripper_length * math.cos(math.radians(theta)), z + 80)
        while True:
            user_input = input("輸入 1 繼續下一步動作，或按 q 退出: ")
            if user_input == "1":
                print("✓ 繼續執行...")
            
                break 
            elif user_input.lower() == "q":
                print("✗ 取消動作")
                exit()
            else:
                print("⚠ 請輸入 1 或 q")
        if x >= 530:
            self.pos_single_move(arm, ox, oy, oz, x-150, y , z + 80)
          
           
        while True:
            user_input = input("輸入 1 繼續下一步動作，或按 q 退出: ")
            if user_input == "1":
                print("✓ 繼續執行...")
            
                break 
            elif user_input.lower() == "q":
                print("✗ 取消動作")
                exit()
            else:
                print("⚠ 請輸入 1 或 q")
        self.pos_single_move(arm, ox, oy, oz, 380, sign * 150 , z + 80)
