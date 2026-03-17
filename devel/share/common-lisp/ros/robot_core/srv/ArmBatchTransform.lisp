; Auto-generated. Do not edit!


(cl:in-package robot_core-srv)


;//! \htmlinclude ArmBatchTransform-request.msg.html

(cl:defclass <ArmBatchTransform-request> (roslisp-msg-protocol:ros-message)
  ((ids
    :reader ids
    :initarg :ids
    :type (cl:vector cl:integer)
   :initform (cl:make-array 0 :element-type 'cl:integer :initial-element 0))
   (points
    :reader points
    :initarg :points
    :type (cl:vector geometry_msgs-msg:Point)
   :initform (cl:make-array 0 :element-type 'geometry_msgs-msg:Point :initial-element (cl:make-instance 'geometry_msgs-msg:Point)))
   (arm
    :reader arm
    :initarg :arm
    :type cl:integer
    :initform 0))
)

(cl:defclass ArmBatchTransform-request (<ArmBatchTransform-request>)
  ())

(cl:defmethod cl:initialize-instance :after ((m <ArmBatchTransform-request>) cl:&rest args)
  (cl:declare (cl:ignorable args))
  (cl:unless (cl:typep m 'ArmBatchTransform-request)
    (roslisp-msg-protocol:msg-deprecation-warning "using old message class name robot_core-srv:<ArmBatchTransform-request> is deprecated: use robot_core-srv:ArmBatchTransform-request instead.")))

(cl:ensure-generic-function 'ids-val :lambda-list '(m))
(cl:defmethod ids-val ((m <ArmBatchTransform-request>))
  (roslisp-msg-protocol:msg-deprecation-warning "Using old-style slot reader robot_core-srv:ids-val is deprecated.  Use robot_core-srv:ids instead.")
  (ids m))

(cl:ensure-generic-function 'points-val :lambda-list '(m))
(cl:defmethod points-val ((m <ArmBatchTransform-request>))
  (roslisp-msg-protocol:msg-deprecation-warning "Using old-style slot reader robot_core-srv:points-val is deprecated.  Use robot_core-srv:points instead.")
  (points m))

(cl:ensure-generic-function 'arm-val :lambda-list '(m))
(cl:defmethod arm-val ((m <ArmBatchTransform-request>))
  (roslisp-msg-protocol:msg-deprecation-warning "Using old-style slot reader robot_core-srv:arm-val is deprecated.  Use robot_core-srv:arm instead.")
  (arm m))
(cl:defmethod roslisp-msg-protocol:serialize ((msg <ArmBatchTransform-request>) ostream)
  "Serializes a message object of type '<ArmBatchTransform-request>"
  (cl:let ((__ros_arr_len (cl:length (cl:slot-value msg 'ids))))
    (cl:write-byte (cl:ldb (cl:byte 8 0) __ros_arr_len) ostream)
    (cl:write-byte (cl:ldb (cl:byte 8 8) __ros_arr_len) ostream)
    (cl:write-byte (cl:ldb (cl:byte 8 16) __ros_arr_len) ostream)
    (cl:write-byte (cl:ldb (cl:byte 8 24) __ros_arr_len) ostream))
  (cl:map cl:nil #'(cl:lambda (ele) (cl:write-byte (cl:ldb (cl:byte 8 0) ele) ostream)
  (cl:write-byte (cl:ldb (cl:byte 8 8) ele) ostream)
  (cl:write-byte (cl:ldb (cl:byte 8 16) ele) ostream)
  (cl:write-byte (cl:ldb (cl:byte 8 24) ele) ostream))
   (cl:slot-value msg 'ids))
  (cl:let ((__ros_arr_len (cl:length (cl:slot-value msg 'points))))
    (cl:write-byte (cl:ldb (cl:byte 8 0) __ros_arr_len) ostream)
    (cl:write-byte (cl:ldb (cl:byte 8 8) __ros_arr_len) ostream)
    (cl:write-byte (cl:ldb (cl:byte 8 16) __ros_arr_len) ostream)
    (cl:write-byte (cl:ldb (cl:byte 8 24) __ros_arr_len) ostream))
  (cl:map cl:nil #'(cl:lambda (ele) (roslisp-msg-protocol:serialize ele ostream))
   (cl:slot-value msg 'points))
  (cl:write-byte (cl:ldb (cl:byte 8 0) (cl:slot-value msg 'arm)) ostream)
  (cl:write-byte (cl:ldb (cl:byte 8 8) (cl:slot-value msg 'arm)) ostream)
  (cl:write-byte (cl:ldb (cl:byte 8 16) (cl:slot-value msg 'arm)) ostream)
  (cl:write-byte (cl:ldb (cl:byte 8 24) (cl:slot-value msg 'arm)) ostream)
)
(cl:defmethod roslisp-msg-protocol:deserialize ((msg <ArmBatchTransform-request>) istream)
  "Deserializes a message object of type '<ArmBatchTransform-request>"
  (cl:let ((__ros_arr_len 0))
    (cl:setf (cl:ldb (cl:byte 8 0) __ros_arr_len) (cl:read-byte istream))
    (cl:setf (cl:ldb (cl:byte 8 8) __ros_arr_len) (cl:read-byte istream))
    (cl:setf (cl:ldb (cl:byte 8 16) __ros_arr_len) (cl:read-byte istream))
    (cl:setf (cl:ldb (cl:byte 8 24) __ros_arr_len) (cl:read-byte istream))
  (cl:setf (cl:slot-value msg 'ids) (cl:make-array __ros_arr_len))
  (cl:let ((vals (cl:slot-value msg 'ids)))
    (cl:dotimes (i __ros_arr_len)
    (cl:setf (cl:ldb (cl:byte 8 0) (cl:aref vals i)) (cl:read-byte istream))
    (cl:setf (cl:ldb (cl:byte 8 8) (cl:aref vals i)) (cl:read-byte istream))
    (cl:setf (cl:ldb (cl:byte 8 16) (cl:aref vals i)) (cl:read-byte istream))
    (cl:setf (cl:ldb (cl:byte 8 24) (cl:aref vals i)) (cl:read-byte istream)))))
  (cl:let ((__ros_arr_len 0))
    (cl:setf (cl:ldb (cl:byte 8 0) __ros_arr_len) (cl:read-byte istream))
    (cl:setf (cl:ldb (cl:byte 8 8) __ros_arr_len) (cl:read-byte istream))
    (cl:setf (cl:ldb (cl:byte 8 16) __ros_arr_len) (cl:read-byte istream))
    (cl:setf (cl:ldb (cl:byte 8 24) __ros_arr_len) (cl:read-byte istream))
  (cl:setf (cl:slot-value msg 'points) (cl:make-array __ros_arr_len))
  (cl:let ((vals (cl:slot-value msg 'points)))
    (cl:dotimes (i __ros_arr_len)
    (cl:setf (cl:aref vals i) (cl:make-instance 'geometry_msgs-msg:Point))
  (roslisp-msg-protocol:deserialize (cl:aref vals i) istream))))
    (cl:setf (cl:ldb (cl:byte 8 0) (cl:slot-value msg 'arm)) (cl:read-byte istream))
    (cl:setf (cl:ldb (cl:byte 8 8) (cl:slot-value msg 'arm)) (cl:read-byte istream))
    (cl:setf (cl:ldb (cl:byte 8 16) (cl:slot-value msg 'arm)) (cl:read-byte istream))
    (cl:setf (cl:ldb (cl:byte 8 24) (cl:slot-value msg 'arm)) (cl:read-byte istream))
  msg
)
(cl:defmethod roslisp-msg-protocol:ros-datatype ((msg (cl:eql '<ArmBatchTransform-request>)))
  "Returns string type for a service object of type '<ArmBatchTransform-request>"
  "robot_core/ArmBatchTransformRequest")
(cl:defmethod roslisp-msg-protocol:ros-datatype ((msg (cl:eql 'ArmBatchTransform-request)))
  "Returns string type for a service object of type 'ArmBatchTransform-request"
  "robot_core/ArmBatchTransformRequest")
(cl:defmethod roslisp-msg-protocol:md5sum ((type (cl:eql '<ArmBatchTransform-request>)))
  "Returns md5sum for a message object of type '<ArmBatchTransform-request>"
  "6007fc72702fa9d4c127d034c134e06f")
(cl:defmethod roslisp-msg-protocol:md5sum ((type (cl:eql 'ArmBatchTransform-request)))
  "Returns md5sum for a message object of type 'ArmBatchTransform-request"
  "6007fc72702fa9d4c127d034c134e06f")
(cl:defmethod roslisp-msg-protocol:message-definition ((type (cl:eql '<ArmBatchTransform-request>)))
  "Returns full string definition for message of type '<ArmBatchTransform-request>"
  (cl:format cl:nil "# === Request (Python 發送給 C++ 的請求) ===~%# 每個物體的唯一 ID (用來對應 shared_object 的 index)~%uint32[] ids~%~%# 相機座標列表 (對應上面的 ids)~%geometry_msgs/Point[] points~%~%# arm id(1:left,2:right)~%uint32 arm~%~%================================================================================~%MSG: geometry_msgs/Point~%# This contains the position of a point in free space~%float64 x~%float64 y~%float64 z~%~%~%"))
(cl:defmethod roslisp-msg-protocol:message-definition ((type (cl:eql 'ArmBatchTransform-request)))
  "Returns full string definition for message of type 'ArmBatchTransform-request"
  (cl:format cl:nil "# === Request (Python 發送給 C++ 的請求) ===~%# 每個物體的唯一 ID (用來對應 shared_object 的 index)~%uint32[] ids~%~%# 相機座標列表 (對應上面的 ids)~%geometry_msgs/Point[] points~%~%# arm id(1:left,2:right)~%uint32 arm~%~%================================================================================~%MSG: geometry_msgs/Point~%# This contains the position of a point in free space~%float64 x~%float64 y~%float64 z~%~%~%"))
(cl:defmethod roslisp-msg-protocol:serialization-length ((msg <ArmBatchTransform-request>))
  (cl:+ 0
     4 (cl:reduce #'cl:+ (cl:slot-value msg 'ids) :key #'(cl:lambda (ele) (cl:declare (cl:ignorable ele)) (cl:+ 4)))
     4 (cl:reduce #'cl:+ (cl:slot-value msg 'points) :key #'(cl:lambda (ele) (cl:declare (cl:ignorable ele)) (cl:+ (roslisp-msg-protocol:serialization-length ele))))
     4
))
(cl:defmethod roslisp-msg-protocol:ros-message-to-list ((msg <ArmBatchTransform-request>))
  "Converts a ROS message object to a list"
  (cl:list 'ArmBatchTransform-request
    (cl:cons ':ids (ids msg))
    (cl:cons ':points (points msg))
    (cl:cons ':arm (arm msg))
))
;//! \htmlinclude ArmBatchTransform-response.msg.html

(cl:defclass <ArmBatchTransform-response> (roslisp-msg-protocol:ros-message)
  ((ids
    :reader ids
    :initarg :ids
    :type (cl:vector cl:integer)
   :initform (cl:make-array 0 :element-type 'cl:integer :initial-element 0))
   (points
    :reader points
    :initarg :points
    :type (cl:vector geometry_msgs-msg:Point)
   :initform (cl:make-array 0 :element-type 'geometry_msgs-msg:Point :initial-element (cl:make-instance 'geometry_msgs-msg:Point)))
   (success
    :reader success
    :initarg :success
    :type cl:boolean
    :initform cl:nil))
)

(cl:defclass ArmBatchTransform-response (<ArmBatchTransform-response>)
  ())

(cl:defmethod cl:initialize-instance :after ((m <ArmBatchTransform-response>) cl:&rest args)
  (cl:declare (cl:ignorable args))
  (cl:unless (cl:typep m 'ArmBatchTransform-response)
    (roslisp-msg-protocol:msg-deprecation-warning "using old message class name robot_core-srv:<ArmBatchTransform-response> is deprecated: use robot_core-srv:ArmBatchTransform-response instead.")))

(cl:ensure-generic-function 'ids-val :lambda-list '(m))
(cl:defmethod ids-val ((m <ArmBatchTransform-response>))
  (roslisp-msg-protocol:msg-deprecation-warning "Using old-style slot reader robot_core-srv:ids-val is deprecated.  Use robot_core-srv:ids instead.")
  (ids m))

(cl:ensure-generic-function 'points-val :lambda-list '(m))
(cl:defmethod points-val ((m <ArmBatchTransform-response>))
  (roslisp-msg-protocol:msg-deprecation-warning "Using old-style slot reader robot_core-srv:points-val is deprecated.  Use robot_core-srv:points instead.")
  (points m))

(cl:ensure-generic-function 'success-val :lambda-list '(m))
(cl:defmethod success-val ((m <ArmBatchTransform-response>))
  (roslisp-msg-protocol:msg-deprecation-warning "Using old-style slot reader robot_core-srv:success-val is deprecated.  Use robot_core-srv:success instead.")
  (success m))
(cl:defmethod roslisp-msg-protocol:serialize ((msg <ArmBatchTransform-response>) ostream)
  "Serializes a message object of type '<ArmBatchTransform-response>"
  (cl:let ((__ros_arr_len (cl:length (cl:slot-value msg 'ids))))
    (cl:write-byte (cl:ldb (cl:byte 8 0) __ros_arr_len) ostream)
    (cl:write-byte (cl:ldb (cl:byte 8 8) __ros_arr_len) ostream)
    (cl:write-byte (cl:ldb (cl:byte 8 16) __ros_arr_len) ostream)
    (cl:write-byte (cl:ldb (cl:byte 8 24) __ros_arr_len) ostream))
  (cl:map cl:nil #'(cl:lambda (ele) (cl:write-byte (cl:ldb (cl:byte 8 0) ele) ostream)
  (cl:write-byte (cl:ldb (cl:byte 8 8) ele) ostream)
  (cl:write-byte (cl:ldb (cl:byte 8 16) ele) ostream)
  (cl:write-byte (cl:ldb (cl:byte 8 24) ele) ostream))
   (cl:slot-value msg 'ids))
  (cl:let ((__ros_arr_len (cl:length (cl:slot-value msg 'points))))
    (cl:write-byte (cl:ldb (cl:byte 8 0) __ros_arr_len) ostream)
    (cl:write-byte (cl:ldb (cl:byte 8 8) __ros_arr_len) ostream)
    (cl:write-byte (cl:ldb (cl:byte 8 16) __ros_arr_len) ostream)
    (cl:write-byte (cl:ldb (cl:byte 8 24) __ros_arr_len) ostream))
  (cl:map cl:nil #'(cl:lambda (ele) (roslisp-msg-protocol:serialize ele ostream))
   (cl:slot-value msg 'points))
  (cl:write-byte (cl:ldb (cl:byte 8 0) (cl:if (cl:slot-value msg 'success) 1 0)) ostream)
)
(cl:defmethod roslisp-msg-protocol:deserialize ((msg <ArmBatchTransform-response>) istream)
  "Deserializes a message object of type '<ArmBatchTransform-response>"
  (cl:let ((__ros_arr_len 0))
    (cl:setf (cl:ldb (cl:byte 8 0) __ros_arr_len) (cl:read-byte istream))
    (cl:setf (cl:ldb (cl:byte 8 8) __ros_arr_len) (cl:read-byte istream))
    (cl:setf (cl:ldb (cl:byte 8 16) __ros_arr_len) (cl:read-byte istream))
    (cl:setf (cl:ldb (cl:byte 8 24) __ros_arr_len) (cl:read-byte istream))
  (cl:setf (cl:slot-value msg 'ids) (cl:make-array __ros_arr_len))
  (cl:let ((vals (cl:slot-value msg 'ids)))
    (cl:dotimes (i __ros_arr_len)
    (cl:setf (cl:ldb (cl:byte 8 0) (cl:aref vals i)) (cl:read-byte istream))
    (cl:setf (cl:ldb (cl:byte 8 8) (cl:aref vals i)) (cl:read-byte istream))
    (cl:setf (cl:ldb (cl:byte 8 16) (cl:aref vals i)) (cl:read-byte istream))
    (cl:setf (cl:ldb (cl:byte 8 24) (cl:aref vals i)) (cl:read-byte istream)))))
  (cl:let ((__ros_arr_len 0))
    (cl:setf (cl:ldb (cl:byte 8 0) __ros_arr_len) (cl:read-byte istream))
    (cl:setf (cl:ldb (cl:byte 8 8) __ros_arr_len) (cl:read-byte istream))
    (cl:setf (cl:ldb (cl:byte 8 16) __ros_arr_len) (cl:read-byte istream))
    (cl:setf (cl:ldb (cl:byte 8 24) __ros_arr_len) (cl:read-byte istream))
  (cl:setf (cl:slot-value msg 'points) (cl:make-array __ros_arr_len))
  (cl:let ((vals (cl:slot-value msg 'points)))
    (cl:dotimes (i __ros_arr_len)
    (cl:setf (cl:aref vals i) (cl:make-instance 'geometry_msgs-msg:Point))
  (roslisp-msg-protocol:deserialize (cl:aref vals i) istream))))
    (cl:setf (cl:slot-value msg 'success) (cl:not (cl:zerop (cl:read-byte istream))))
  msg
)
(cl:defmethod roslisp-msg-protocol:ros-datatype ((msg (cl:eql '<ArmBatchTransform-response>)))
  "Returns string type for a service object of type '<ArmBatchTransform-response>"
  "robot_core/ArmBatchTransformResponse")
(cl:defmethod roslisp-msg-protocol:ros-datatype ((msg (cl:eql 'ArmBatchTransform-response)))
  "Returns string type for a service object of type 'ArmBatchTransform-response"
  "robot_core/ArmBatchTransformResponse")
(cl:defmethod roslisp-msg-protocol:md5sum ((type (cl:eql '<ArmBatchTransform-response>)))
  "Returns md5sum for a message object of type '<ArmBatchTransform-response>"
  "6007fc72702fa9d4c127d034c134e06f")
(cl:defmethod roslisp-msg-protocol:md5sum ((type (cl:eql 'ArmBatchTransform-response)))
  "Returns md5sum for a message object of type 'ArmBatchTransform-response"
  "6007fc72702fa9d4c127d034c134e06f")
(cl:defmethod roslisp-msg-protocol:message-definition ((type (cl:eql '<ArmBatchTransform-response>)))
  "Returns full string definition for message of type '<ArmBatchTransform-response>"
  (cl:format cl:nil "~%# === Response (C++ 回傳給 Python 的結果) ===~%# 回傳 ID 以確保順序正確 (通常跟請求的一樣)~%uint32[] ids~%~%# 轉換後的基座標列表~%geometry_msgs/Point[] points~%~%# 是否執行成功~%bool success~%~%================================================================================~%MSG: geometry_msgs/Point~%# This contains the position of a point in free space~%float64 x~%float64 y~%float64 z~%~%~%"))
(cl:defmethod roslisp-msg-protocol:message-definition ((type (cl:eql 'ArmBatchTransform-response)))
  "Returns full string definition for message of type 'ArmBatchTransform-response"
  (cl:format cl:nil "~%# === Response (C++ 回傳給 Python 的結果) ===~%# 回傳 ID 以確保順序正確 (通常跟請求的一樣)~%uint32[] ids~%~%# 轉換後的基座標列表~%geometry_msgs/Point[] points~%~%# 是否執行成功~%bool success~%~%================================================================================~%MSG: geometry_msgs/Point~%# This contains the position of a point in free space~%float64 x~%float64 y~%float64 z~%~%~%"))
(cl:defmethod roslisp-msg-protocol:serialization-length ((msg <ArmBatchTransform-response>))
  (cl:+ 0
     4 (cl:reduce #'cl:+ (cl:slot-value msg 'ids) :key #'(cl:lambda (ele) (cl:declare (cl:ignorable ele)) (cl:+ 4)))
     4 (cl:reduce #'cl:+ (cl:slot-value msg 'points) :key #'(cl:lambda (ele) (cl:declare (cl:ignorable ele)) (cl:+ (roslisp-msg-protocol:serialization-length ele))))
     1
))
(cl:defmethod roslisp-msg-protocol:ros-message-to-list ((msg <ArmBatchTransform-response>))
  "Converts a ROS message object to a list"
  (cl:list 'ArmBatchTransform-response
    (cl:cons ':ids (ids msg))
    (cl:cons ':points (points msg))
    (cl:cons ':success (success msg))
))
(cl:defmethod roslisp-msg-protocol:service-request-type ((msg (cl:eql 'ArmBatchTransform)))
  'ArmBatchTransform-request)
(cl:defmethod roslisp-msg-protocol:service-response-type ((msg (cl:eql 'ArmBatchTransform)))
  'ArmBatchTransform-response)
(cl:defmethod roslisp-msg-protocol:ros-datatype ((msg (cl:eql 'ArmBatchTransform)))
  "Returns string type for a service object of type '<ArmBatchTransform>"
  "robot_core/ArmBatchTransform")