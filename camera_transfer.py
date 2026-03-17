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
from dotenv import load_dotenv
from typing import List
from robot_core.srv import BatchTransform, BatchTransformRequest, ArmBatchTransform, ArmBatchTransformRequest
print("✓ robot_core 导入完成，md5sum:", BatchTransform._md5sum)



class CameraTransfer:
    # def __init__(self):
        # rospy.init_node('camera_transfer', anonymous=True)
        
    def camera_to_ee_transform(self, camera_id, point_camera_mm): 
        # horizontal_offset = 29 #mm
        vertical_offset = 57.5 #mm
        
        camera_offset_x = 31 #mm 30
        z_offset = 87.32 #mm 62.32 72.32
        if camera_id == 0:
            """頭相機座標轉脖子末端座標"""
            X_camera, Y_camera, Z_camera = point_camera_mm
            
            X_ee = Z_camera
            Y_ee = -X_camera + camera_offset_x
            Z_ee = -Y_camera

                

        elif camera_id == 1:
            """左相機座標轉末端座標"""
            X_camera, Y_camera, Z_camera = point_camera_mm
            X_ee = -X_camera + camera_offset_x
            Y_ee = -Y_camera + vertical_offset
            Z_ee =  Z_camera - z_offset
            # X_ee = Y_camera + horizontal_offset
            # Y_ee = X_camera + vertical_offset
            # Z_ee =  Z_camera - z_offset

        elif camera_id == 2:
            """右相機座標轉末端座標"""
            X_camera, Y_camera, Z_camera = point_camera_mm
            X_ee = -X_camera + camera_offset_x
            Y_ee = -Y_camera + vertical_offset
            Z_ee = Z_camera - z_offset
            # X_ee = Y_camera + horizontal_offset
            # Y_ee = X_camera + vertical_offset
            # Z_ee =  Z_camera - z_offset
        return [X_ee, Y_ee, Z_ee]
    def dict_transform_points(self, camera_id, obj_dict, input_field="camera pos", output_field="world pos"):
        if input_field not in obj_dict:
            rospy.logwarn(f"字典中缺少輸入欄位 '{input_field}'，無法進行轉換。")
            return False
        
        if camera_id == 0:
            success = self.head_transform_points_service(obj_dict, input_field=input_field, output_field=output_field, service_name='batch_transform')
        else:
            success = self.arm_transform_points_service(obj_dict, camera_id, input_field=input_field, output_field=output_field, service_name='Arm_batch_transform')
        return success
        
    def list_transform_points(self, camera_id, point_camera_mm):
        object = {
            "name": "object",
            "camera pos": point_camera_mm,
        }
        if camera_id == 0:
            success = self.head_transform_points_service(object, input_field="camera pos", output_field="world pos", service_name='batch_transform')
        else:
            success = self.arm_transform_points_service(object, camera_id, input_field="camera pos", output_field="world pos", service_name='Arm_batch_transform')
        if not success:
            rospy.logerr("座標轉換失敗")
        return object.get("world pos", None)

    def head_transform_points_service(self, obj_dict, input_field="camera pos", output_field="world pos", service_name='batch_transform'):
        """
        將單一物件字典中的相機座標轉換為世界座標 (通常用於頭部相機/整體環境轉換)。
        
        Args:
            obj_dict (dict): 包含物件資訊的字典 (需包含 input_field 指定的鍵)
            input_field (str): 要轉換的輸入座標鍵名，預設為 "camera pos"
            output_field (str): 轉換後的輸出座標鍵名，預設為 "world pos"
            service_name (str): ROS Service 名稱，預設為 'batch_transform'
        
        Returns:
            bool: 轉換是否成功 (True/False)
        """
        rospy.wait_for_service(service_name)
        
        # 1. 檢查輸入資料是否合法
        if input_field not in obj_dict:
            rospy.logwarn(f"字典中缺少輸入欄位 '{input_field}'，無法進行轉換。")
            return False
       
        
        pos_data = obj_dict[input_field]
        if len(pos_data) < 3:
            rospy.logwarn(f"'{input_field}' 座標長度小於 3，無法轉換: {pos_data}")
            return False
        
        # print(f"原始相機座標: {pos_data}")
        pos_data=self.camera_to_ee_transform(0, pos_data)
        # print(f"轉換後的末端座標: {pos_data}")
        try:
            transform_service = rospy.ServiceProxy(service_name, BatchTransform)
            req = BatchTransformRequest()
            
            # 2. 打包資料 (為了符合 C++ 端陣列設計，我們塞入 1 筆資料)
            px, py, pz = pos_data[0:3] 
            req.ids.append(0) # 只有一個物件，ID 固定給 0
            
            p = Point()
            p.x = float(px)
            p.y = float(py)
            p.z = float(pz)
            req.points.append(p)
            
            # 3. 呼叫 Service 
            # (這裡不需要 req.arm，因為 BatchTransform 服務本來就沒這個參數)
            res = transform_service(req)
            
            # 4. 更新字典資料
            if res.success and len(res.points) > 0:
                returned_pt = res.points[0]
                
                # 直接把結果寫回你傳進來的字典裡
                obj_dict[output_field] = [returned_pt.x, returned_pt.y, returned_pt.z]
                
                rospy.loginfo(f"座標轉換成功，寫入 '{output_field}': {obj_dict[output_field]}")
                return True
            else:
                rospy.logwarn(f"Service 回傳失敗或無資料點，轉換失敗。")
                obj_dict[output_field] = None
                return False
                
        except rospy.ServiceException as e:
            rospy.logerr(f"ROS Service 通訊失敗: {e}")
            obj_dict[output_field] = None
            return False
        except Exception as e:
            rospy.logerr(f"Python 處理發生錯誤: {e}")
            obj_dict[output_field] = None
            return False


    def arm_transform_points_service(self, obj_dict, arm_id, input_field="camera pos", output_field="world pos", service_name='Arm_batch_transform'):
        """
        將單一物件字典中的相機座標轉換為世界座標。
        
        Args:
            obj_dict (dict): 包含物件資訊的字典 (需包含 input_field 指定的鍵)
            arm_id (int): 1 代表左手, 2 代表右手
            input_field (str): 要轉換的輸入座標鍵名，預設為 "camera pos"
            output_field (str): 轉換後的輸出座標鍵名，預設為 "world pos"
            service_name (str): ROS Service 名稱
        
        Returns:
            bool: 轉換是否成功
        """
        rospy.wait_for_service(service_name)
        
        # 1. 檢查輸入資料是否合法
        if input_field not in obj_dict:
            rospy.logwarn(f"字典中缺少輸入欄位 '{input_field}'，跳過轉換。")
            return False

        pos_data = obj_dict[input_field]
        if len(pos_data) < 3:
            rospy.logwarn(f"'{input_field}' 座標長度小於 3，無法轉換: {pos_data}")
            return False
       
        # print(f"原始相機座標: {pos_data}")
        pos_data=self.camera_to_ee_transform(arm_id, pos_data)
        # print(f"轉換後的末端座標: {pos_data}")
        try:
            transform_service = rospy.ServiceProxy(service_name, ArmBatchTransform)
            req = ArmBatchTransformRequest()
            
            # 2. 打包資料 (為了符合原本 Batch 的設計，只塞入一筆資料)
            px, py, pz = pos_data[0:3] # 只取前三個元素，避免資料過長報錯
            req.arm = arm_id
            req.ids.append(0) # 因為只有一個物件，ID 固定給 0
            
            p = Point()
            p.x = float(px)
            p.y = float(py)
            p.z = float(pz)
            req.points.append(p)
            
            # 3. 呼叫 Service
            res = transform_service(req)
            
            # 4. 更新字典資料
            if res.success and len(res.points) > 0:
                returned_pt = res.points[0]
                # 直接更新傳入的字典
                obj_dict[output_field] = [returned_pt.x, returned_pt.y, returned_pt.z]
                rospy.loginfo(f"座標轉換成功，寫入 '{output_field}': {obj_dict[output_field]}")
                return True
            else:
                rospy.logwarn(f"Service 回傳失敗或無資料點，轉換失敗。")
                obj_dict[output_field] = None
                return False
                
        except rospy.ServiceException as e:
            rospy.logerr(f"Service call failed: {e}")
            obj_dict[output_field] = None
            return False
        except Exception as e:
            rospy.logerr(f"Python processing error: {e}")
            obj_dict[output_field] = None
            return False
