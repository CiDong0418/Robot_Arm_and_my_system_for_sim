
#!/usr/bin/env python3
import rospy
from std_msgs.msg import String
import rospy
import json
import time
from geometry_msgs.msg import Point
from dotenv import load_dotenv
import os
import math
from typing import List
import threading
from actionCommand import PostureCommandPublisher
from camera_transfer import CameraTransfer
rospy.init_node('main_node', anonymous=True)
# from robot_core.srv import BatchTransform, BatchTransformRequest, ArmBatchTransform, ArmBatchTransformRequest
# print("✓ robot_core 导入完成，md5sum:", BatchTransform._md5sum)

robot_control = PostureCommandPublisher()
camera_transfer = CameraTransfer()


if __name__ == '__main__': 
     
    while not rospy.is_shutdown():
        pin = input("number:")
        if pin.lower() == 'q':
            print("✗ 退出程式")
            break
        if pin == "0":
            robot_control.initial_position() # 移動到初始位置
            robot_control.neck_control(0, 35)
        

        
        world_pos = camera_transfer.list_transform_points(0, [76.184, 70.759, 599.000])
        R = 53.126
        print("轉換後的世界座標:", world_pos)
        move_45_deg = 130/math.sqrt(2) # 45度移動距離
        move_90_deg = 130 # 90度移動距離
        move_675_deg_x = 130*math.cos(math.radians(22.5)) # 67.5度移動距離
        move_675_deg_y = 130*math.sin(math.radians(22.5)) # 67.5度移動距離
        if pin == "1":
            robot_control.pos_single_move("right", 0.0, (180-45.0), 0.0,  (world_pos[0] - move_45_deg + R ), (world_pos[1] - move_45_deg ), world_pos[2] -40) # 移動到指定位置                                                                    
                                                                                
            robot_control.pos_single_move("right", 0.0, (180-45.0), 0.0,  world_pos[0] + R -50 , world_pos[1] -50 , world_pos[2] -70)
            robot_control.gripper_control("right", 160) # 設定右手夾爪角度為100

            time.sleep(1)
            

            robot_control.initial_position()
            robot_control.open_gripper("right") # 打開右手夾爪

        elif pin == "2":
            while True:
                xyz_input = input("輸入 oz x, y, z 座標 (以逗號分隔)，或輸入 'q' 退出: ")
                if xyz_input.lower() == 'q':
                    print("✗ 退出程式")
                    break
                try:
                    oz_str, x_str, y_str, z_str = xyz_input.split(' ')
                    oz = float(oz_str.strip())
                    x = float(x_str.strip())
                    y = float(y_str.strip())
                    z = float(z_str.strip())
                    print(f"你輸入的座標是: oz={oz}, x={x}, y={y}, z={z}")
                    robot_control.pos_single_move("right", 0, 180-45.0, oz,  x , y , z) # 移動到指定位置
                except ValueError:
                    print("⚠ 請確保輸入格式正確，例: 100 200 300")
        elif pin == "3":      
            # robot_control.pos_single_move("right", 0.0, (180-67.5), 0.0,  600, -300, -100)
            robot_control.pos_single_move("right", 0.0, (180-38.0), 0.0,  480, -130, -140) # 移動到指定位置
            robot_control.pos_single_move("right", 0.0, (180-38.0), 0.0,  530, -100, -140)
        elif pin == "4":
            robot_control.pos_single_move("right", 0.0, (180-45), 0.0,  650, 0, -50)
            # time.sleep(1)
            robot_control.gripper_control("right", 150) # 設定左手夾爪角度為100
            time.sleep(3)
            robot_control.open_gripper("right") # 打開右手夾爪
            time.sleep(1)
            robot_control.initial_position() # 移動到初始位置
        elif pin == "5":
            robot_control.pos_single_move("left", -180.0, 20.0, 0.0,  420.0, 130.0, -130.0)
        elif pin == "6":
            robot_control.pos_single_move("right", 95.0, 0.0, -90.0,  380, -120, -250)

        elif pin == "7":
            while True:
                x, y, z = map(float, input("x y z: ").split())
                robot_control.pos_single_move("right", 95.0, 0.0, -90.0,  x, y, z)
        elif pin == "8":
            robot_control.gripper_control("right", 160)
        elif pin == "9":
            robot_control.open_gripper("right")
        elif pin == "10":
            while True:
                xyz_input = input("輸入 oz x, y, z 座標 (以逗號分隔)，或輸入 'q' 退出: ")
                if xyz_input.lower() == 'q':
                    print("✗ 退出程式")
                    break
                try:
                    oz_str, x_str, y_str, z_str = xyz_input.split(' ')
                    oz = float(oz_str.strip())
                    x = float(x_str.strip())
                    y = float(y_str.strip())
                    z = float(z_str.strip())
                    print(f"你輸入的座標是: oz={oz}, x={x}, y={y}, z={z}")
                    robot_control.pos_single_move("left", -180, 45.0 , oz,  x , y , z) # 移動到指定位置
                except ValueError:
                    print("⚠ 請確保輸入格式正確，例: 100 200 300")
        elif pin == "11":
            robot_control.initial_position() # 移動到初始位置
            robot_control.open_gripper("left") # 打開左手夾爪
            robot_control.open_gripper("right") # 打開右手夾爪
        elif pin == "12":
            robot_control.pos_single_move("left", -180, 45.0 , 90.0,  420 , 130 , -130) # 移動到指定位置
            time.sleep(1)
            robot_control.pos_single_move("left", None, None , 0.0,  None , None , None) # 移動到指定位置
        elif pin == "13":
            robot_control.pos_single_move("right", 0.0, (180-45.0), 0.0,  600, -130, -140) # 移動到指定位置
            robot_control.open_gripper("right") # 打開右手夾爪
            robot_control.initial_position() # 移動到初始位置
        elif pin == "14":
            robot_control.pos_single_move("right", 0.0, (180-45.0), 0.0,  530, -170, -230) # 移動到指定位置                                                                    
                                                                                
            robot_control.pos_single_move("right", 0.0, (180-45.0), 0.0,  600 , -100 , -230)
            robot_control.gripper_control("right", 160) # 設定右手夾爪角度為100
            robot_control.initial_position() # 移動到初始位置
        elif pin == "15":
            z = input("請輸入夾爪角度 (5 ~ 200): ")
            robot_control.gripper_control("right", int(z)) # 設定右手夾爪角度為100
        elif pin == "16":
            robot_control.open_gripper("right") # 打開右手夾爪

    
    # robot_control.pos_single_move("right", -90.0, 0.0, 0.0,  (world_pos[0] -100.0) , world_pos[1] , world_pos[2]) # 移動到指定位置
    # robot_control.pos_single_move("left", -180.0, 38.0, 0.0,  680, 120, -140 ) # 極限（在38度的時候 且y大約在120）
    # robot_control.pos_single_move("right", 0.0, (180-38.0), 0.0,  480, -130, -140) # 移動到指定位置
    # robot_control.pos_single_move("right", 0.0, (180-38.0), 0.0,  530, -100, -140)

    # ============================== 1. 頸部控制範例 ===================================

    
    # robot_control.neck_control(20, 0) # 向左轉20度
    # robot_control.neck_control(0, 35)
    # ================================================================================
    # while True:
    #     user_input = input("輸入 1 繼續下一步動作，或按 q 退出: ")
    #     if user_input == "1":
    #         print("✓ 繼續執行...")
    #         time.sleep(3)  
    #         break 
    #     elif user_input.lower() == "q":
    #         print("✗ 取消動作")
    #         exit()
    #     else:
    #         print("⚠ 請輸入 1 或 q")

    # robot_control.neck_control(0, 0) # 向下轉45度 
    # ======================== 2. 點到點 姿態 單手手臂控制範例 ============================
    # 夾爪水平
    # robot_control.pos_single_move("left", -180.0, 38.0, 0.0,  480, 130, -140 ) # 移動到指定位置
    # robot_control.pos_single_move("left", -180.0, 38.0, 0.0,  680, 120, -140 ) # 極限（在38度的時候 且y大約在120）
    # robot_control.pos_single_move("right", 0.0, (180-38.0), 0.0,  480, -130, -140) # 移動到指定位置
    # robot_control.pos_single_move("right", 0.0, (180-38.0), 0.0,  530, -100, -140)

    # 夾爪垂直
    # robot_control.pos_single_move("left", -95.0, 0.0, -90.0,  380, 120, -250)
    # robot_control.pos_single_move("right", 95.0, 0.0, -90.0,  380, -120, -250)
    # =================================================================================


    # ================================= 3. 夾爪控制 ====================================
    # robot_control.open_gripper("left") # 打開左手夾爪
    # robot_control.close_gripper("left") # 關閉左手夾爪
    # robot_control.open_gripper("right") # 打開右手夾爪
    # robot_control.close_gripper("right") # 關閉右手夾爪
    # # 夾爪控制（角度控制範例）我都是用 5 ~ 200 角度範圍
    # robot_control.gripper_control("left", 100) # 設定左手夾爪角度為100
    # =================================================================================



    # ============================== 4. 雙手手臂控制範例 =================================
    # robot_control.pos_dual_move(-180.0, 38.0, 0.0,  500, 130, -140, 0.0, (180-38.0), 0.0,  500, -130, -140) # 雙手移動到指定位置  
    # robot_control.initial_position() # 移動到初始位置
    # ==================================================================================


    # ============================== 5. 相機座標轉換 ros 發送與接收 轉換範例 =================================
    # my_object = {
    #     "name": "apple",
    #     "camera pos": [10.5, 20.1, 5.0]
    # }
    # my_objects = [
    #     {
    #         "name": "apple",
    #         "camera pos": [10.5, 20.1, 5.0]
    #     },
    #     {
    #         "name": "sandwich",
    #         "camera pos": [450.5, 120.2, 30.0],
    #         "size": [140, 120, 35]
    #     },
    #     {
    #         "name": "pepper shaker",
    #         "camera pos": [300.0, -50.0, 10.0]
    #     }
    # ]

    # 頭頂相機 左手相機座標轉換 (arm_id=1)  右手相機座標轉換 (arm_id=2)
    # success = camera_transfer.dict_transform_points(0, my_object)
    # success = camera_transfer.dict_transform_points(0, my_objects[1])

    # if success:
    #     print("轉換後的新字典:")
    #     print(my_object) 
    #     # 輸出會自動多出一個 "world pos"：
    #     # {'name': 'apple', 'camera pos': [10.5, 20.1, 5.0], 'world pos': (..., ..., ...)}
    # else:
    #     print("轉換失敗，世界座標可能為 None")
    
    # world_pos = camera_transfer.list_transform_points(0, [450.5, 120.2, 30.0])# 頭頂相機 左手相機座標轉換 (arm_id=1)  右手相機座標轉換 (arm_id=2)
    
    # print("轉換後的世界座標:", world_pos)
    # ==================================================================================


    # ============================== 6. pick 範例 =================================
    # robot_control.pick("left", 520, 100, -190) # theta ： 預設為35.0度
    # robot_control.pick("right", 530, -100, -190)
    # 1. 手臂測試
    time.sleep(2)
    
  
    rospy.spin()
   