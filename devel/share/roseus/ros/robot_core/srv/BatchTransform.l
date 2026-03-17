;; Auto-generated. Do not edit!


(when (boundp 'robot_core::BatchTransform)
  (if (not (find-package "ROBOT_CORE"))
    (make-package "ROBOT_CORE"))
  (shadow 'BatchTransform (find-package "ROBOT_CORE")))
(unless (find-package "ROBOT_CORE::BATCHTRANSFORM")
  (make-package "ROBOT_CORE::BATCHTRANSFORM"))
(unless (find-package "ROBOT_CORE::BATCHTRANSFORMREQUEST")
  (make-package "ROBOT_CORE::BATCHTRANSFORMREQUEST"))
(unless (find-package "ROBOT_CORE::BATCHTRANSFORMRESPONSE")
  (make-package "ROBOT_CORE::BATCHTRANSFORMRESPONSE"))

(in-package "ROS")

(if (not (find-package "GEOMETRY_MSGS"))
  (ros::roseus-add-msgs "geometry_msgs"))


(if (not (find-package "GEOMETRY_MSGS"))
  (ros::roseus-add-msgs "geometry_msgs"))


(defclass robot_core::BatchTransformRequest
  :super ros::object
  :slots (_ids _points ))

(defmethod robot_core::BatchTransformRequest
  (:init
   (&key
    ((:ids __ids) (make-array 0 :initial-element 0 :element-type :integer))
    ((:points __points) ())
    )
   (send-super :init)
   (setq _ids __ids)
   (setq _points __points)
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
  (:serialization-length
   ()
   (+
    ;; uint32[] _ids
    (* 4    (length _ids)) 4
    ;; geometry_msgs/Point[] _points
    (apply #'+ (send-all _points :serialization-length)) 4
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
   ;;
   self)
  )

(defclass robot_core::BatchTransformResponse
  :super ros::object
  :slots (_ids _points _success ))

(defmethod robot_core::BatchTransformResponse
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

(defclass robot_core::BatchTransform
  :super ros::object
  :slots ())

(setf (get robot_core::BatchTransform :md5sum-) "6021b6112a957556fbdf33fd163786a6")
(setf (get robot_core::BatchTransform :datatype-) "robot_core/BatchTransform")
(setf (get robot_core::BatchTransform :request) robot_core::BatchTransformRequest)
(setf (get robot_core::BatchTransform :response) robot_core::BatchTransformResponse)

(defmethod robot_core::BatchTransformRequest
  (:response () (instance robot_core::BatchTransformResponse :init)))

(setf (get robot_core::BatchTransformRequest :md5sum-) "6021b6112a957556fbdf33fd163786a6")
(setf (get robot_core::BatchTransformRequest :datatype-) "robot_core/BatchTransformRequest")
(setf (get robot_core::BatchTransformRequest :definition-)
      "# === Request (Python 發送給 C++ 的請求) ===
# 每個物體的唯一 ID (用來對應 shared_object 的 index)
uint32[] ids

# 相機座標列表 (對應上面的 ids)
geometry_msgs/Point[] points


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

(setf (get robot_core::BatchTransformResponse :md5sum-) "6021b6112a957556fbdf33fd163786a6")
(setf (get robot_core::BatchTransformResponse :datatype-) "robot_core/BatchTransformResponse")
(setf (get robot_core::BatchTransformResponse :definition-)
      "# === Request (Python 發送給 C++ 的請求) ===
# 每個物體的唯一 ID (用來對應 shared_object 的 index)
uint32[] ids

# 相機座標列表 (對應上面的 ids)
geometry_msgs/Point[] points


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



(provide :robot_core/BatchTransform "6021b6112a957556fbdf33fd163786a6")


