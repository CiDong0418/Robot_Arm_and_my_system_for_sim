;; Auto-generated. Do not edit!


(when (boundp 'robot_core::ArmBatchTransform)
  (if (not (find-package "ROBOT_CORE"))
    (make-package "ROBOT_CORE"))
  (shadow 'ArmBatchTransform (find-package "ROBOT_CORE")))
(unless (find-package "ROBOT_CORE::ARMBATCHTRANSFORM")
  (make-package "ROBOT_CORE::ARMBATCHTRANSFORM"))
(unless (find-package "ROBOT_CORE::ARMBATCHTRANSFORMREQUEST")
  (make-package "ROBOT_CORE::ARMBATCHTRANSFORMREQUEST"))
(unless (find-package "ROBOT_CORE::ARMBATCHTRANSFORMRESPONSE")
  (make-package "ROBOT_CORE::ARMBATCHTRANSFORMRESPONSE"))

(in-package "ROS")

(if (not (find-package "GEOMETRY_MSGS"))
  (ros::roseus-add-msgs "geometry_msgs"))


(if (not (find-package "GEOMETRY_MSGS"))
  (ros::roseus-add-msgs "geometry_msgs"))


(defclass robot_core::ArmBatchTransformRequest
  :super ros::object
  :slots (_ids _points _arm ))

(defmethod robot_core::ArmBatchTransformRequest
  (:init
   (&key
    ((:ids __ids) (make-array 0 :initial-element 0 :element-type :integer))
    ((:points __points) ())
    ((:arm __arm) 0)
    )
   (send-super :init)
   (setq _ids __ids)
   (setq _points __points)
   (setq _arm (round __arm))
   self)
  (:ids
   (&optional __ids)
   (if __ids (setq _ids __ids)) _ids)
  (:points
   (&rest __points)
   (if (keywordp (car __points))
       (send* _points __points)
     (progn
       (if __points (setq _points (car __points)))
       _points)))
  (:arm
   (&optional __arm)
   (if __arm (setq _arm __arm)) _arm)
  (:serialization-length
   ()
   (+
    ;; uint32[] _ids
    (* 4    (length _ids)) 4
    ;; geometry_msgs/Point[] _points
    (apply #'+ (send-all _points :serialization-length)) 4
    ;; uint32 _arm
    4
    ))
  (:serialize
   (&optional strm)
   (let ((s (if strm strm
              (make-string-output-stream (send self :serialization-length)))))
     ;; uint32[] _ids
     (write-long (length _ids) s)
     (dotimes (i (length _ids))
       (write-long (elt _ids i) s)
       )
     ;; geometry_msgs/Point[] _points
     (write-long (length _points) s)
     (dolist (elem _points)
       (send elem :serialize s)
       )
     ;; uint32 _arm
       (write-long _arm s)
     ;;
     (if (null strm) (get-output-stream-string s))))
  (:deserialize
   (buf &optional (ptr- 0))
   ;; uint32[] _ids
   (let (n)
     (setq n (sys::peek buf ptr- :integer)) (incf ptr- 4)
     (setq _ids (instantiate integer-vector n))
     (dotimes (i n)
     (setf (elt _ids i) (sys::peek buf ptr- :integer)) (incf ptr- 4)
     ))
   ;; geometry_msgs/Point[] _points
   (let (n)
     (setq n (sys::peek buf ptr- :integer)) (incf ptr- 4)
     (setq _points (let (r) (dotimes (i n) (push (instance geometry_msgs::Point :init) r)) r))
     (dolist (elem- _points)
     (send elem- :deserialize buf ptr-) (incf ptr- (send elem- :serialization-length))
     ))
   ;; uint32 _arm
     (setq _arm (sys::peek buf ptr- :integer)) (incf ptr- 4)
   ;;
   self)
  )

(defclass robot_core::ArmBatchTransformResponse
  :super ros::object
  :slots (_ids _points _success ))

(defmethod robot_core::ArmBatchTransformResponse
  (:init
   (&key
    ((:ids __ids) (make-array 0 :initial-element 0 :element-type :integer))
    ((:points __points) ())
    ((:success __success) nil)
    )
   (send-super :init)
   (setq _ids __ids)
   (setq _points __points)
   (setq _success __success)
   self)
  (:ids
   (&optional __ids)
   (if __ids (setq _ids __ids)) _ids)
  (:points
   (&rest __points)
   (if (keywordp (car __points))
       (send* _points __points)
     (progn
       (if __points (setq _points (car __points)))
       _points)))
  (:success
   (&optional (__success :null))
   (if (not (eq __success :null)) (setq _success __success)) _success)
  (:serialization-length
   ()
   (+
    ;; uint32[] _ids
    (* 4    (length _ids)) 4
    ;; geometry_msgs/Point[] _points
    (apply #'+ (send-all _points :serialization-length)) 4
    ;; bool _success
    1
    ))
  (:serialize
   (&optional strm)
   (let ((s (if strm strm
              (make-string-output-stream (send self :serialization-length)))))
     ;; uint32[] _ids
     (write-long (length _ids) s)
     (dotimes (i (length _ids))
       (write-long (elt _ids i) s)
       )
     ;; geometry_msgs/Point[] _points
     (write-long (length _points) s)
     (dolist (elem _points)
       (send elem :serialize s)
       )
     ;; bool _success
       (if _success (write-byte -1 s) (write-byte 0 s))
     ;;
     (if (null strm) (get-output-stream-string s))))
  (:deserialize
   (buf &optional (ptr- 0))
   ;; uint32[] _ids
   (let (n)
     (setq n (sys::peek buf ptr- :integer)) (incf ptr- 4)
     (setq _ids (instantiate integer-vector n))
     (dotimes (i n)
     (setf (elt _ids i) (sys::peek buf ptr- :integer)) (incf ptr- 4)
     ))
   ;; geometry_msgs/Point[] _points
   (let (n)
     (setq n (sys::peek buf ptr- :integer)) (incf ptr- 4)
     (setq _points (let (r) (dotimes (i n) (push (instance geometry_msgs::Point :init) r)) r))
     (dolist (elem- _points)
     (send elem- :deserialize buf ptr-) (incf ptr- (send elem- :serialization-length))
     ))
   ;; bool _success
     (setq _success (not (= 0 (sys::peek buf ptr- :char)))) (incf ptr- 1)
   ;;
   self)
  )

(defclass robot_core::ArmBatchTransform
  :super ros::object
  :slots ())

(setf (get robot_core::ArmBatchTransform :md5sum-) "6007fc72702fa9d4c127d034c134e06f")
(setf (get robot_core::ArmBatchTransform :datatype-) "robot_core/ArmBatchTransform")
(setf (get robot_core::ArmBatchTransform :request) robot_core::ArmBatchTransformRequest)
(setf (get robot_core::ArmBatchTransform :response) robot_core::ArmBatchTransformResponse)

(defmethod robot_core::ArmBatchTransformRequest
  (:response () (instance robot_core::ArmBatchTransformResponse :init)))

(setf (get robot_core::ArmBatchTransformRequest :md5sum-) "6007fc72702fa9d4c127d034c134e06f")
(setf (get robot_core::ArmBatchTransformRequest :datatype-) "robot_core/ArmBatchTransformRequest")
(setf (get robot_core::ArmBatchTransformRequest :definition-)
      "# === Request (Python 發送給 C++ 的請求) ===
# 每個物體的唯一 ID (用來對應 shared_object 的 index)
uint32[] ids

# 相機座標列表 (對應上面的 ids)
geometry_msgs/Point[] points

# arm id(1:left,2:right)
uint32 arm

================================================================================
MSG: geometry_msgs/Point
# This contains the position of a point in free space
float64 x
float64 y
float64 z
---

# === Response (C++ 回傳給 Python 的結果) ===
# 回傳 ID 以確保順序正確 (通常跟請求的一樣)
uint32[] ids

# 轉換後的基座標列表
geometry_msgs/Point[] points

# 是否執行成功
bool success

================================================================================
MSG: geometry_msgs/Point
# This contains the position of a point in free space
float64 x
float64 y
float64 z
")

(setf (get robot_core::ArmBatchTransformResponse :md5sum-) "6007fc72702fa9d4c127d034c134e06f")
(setf (get robot_core::ArmBatchTransformResponse :datatype-) "robot_core/ArmBatchTransformResponse")
(setf (get robot_core::ArmBatchTransformResponse :definition-)
      "# === Request (Python 發送給 C++ 的請求) ===
# 每個物體的唯一 ID (用來對應 shared_object 的 index)
uint32[] ids

# 相機座標列表 (對應上面的 ids)
geometry_msgs/Point[] points

# arm id(1:left,2:right)
uint32 arm

================================================================================
MSG: geometry_msgs/Point
# This contains the position of a point in free space
float64 x
float64 y
float64 z
---

# === Response (C++ 回傳給 Python 的結果) ===
# 回傳 ID 以確保順序正確 (通常跟請求的一樣)
uint32[] ids

# 轉換後的基座標列表
geometry_msgs/Point[] points

# 是否執行成功
bool success

================================================================================
MSG: geometry_msgs/Point
# This contains the position of a point in free space
float64 x
float64 y
float64 z
")



(provide :robot_core/ArmBatchTransform "6007fc72702fa9d4c127d034c134e06f")


