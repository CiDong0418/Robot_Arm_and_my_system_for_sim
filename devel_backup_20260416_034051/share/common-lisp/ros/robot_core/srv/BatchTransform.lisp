; Auto-generated. Do not edit!


(cl:in-package robot_core-srv)


;//! \htmlinclude BatchTransform-request.msg.html

(cl:defclass <BatchTransform-request> (roslisp-msg-protocol:ros-message)
  ((ids
    :reader ids
    :initarg :ids
    :type (cl:vector cl:integer)
   :initform (cl:make-array 0 :element-type 'cl:integer :initial-element 0))
   (points
    :reader points
    :initarg :points
    :type (cl:vector geometry_msgs-msg:Point)
   :initform (cl:make-array 0 :element-type 'geometry_msgs-msg:Point :initial-element (cl:make-instance 'geometry_msgs-msg:Point))))
)

(cl:defclass BatchTransform-request (<BatchTransform-request>)
  ())

(cl:defmethod cl:initialize-instance :after ((m <BatchTransform-request>) cl:&rest args)
  (cl:declare (cl:ignorable args))
  (cl:unless (cl:typep m 'BatchTransform-request)
    (roslisp-msg-protocol:msg-deprecation-warning "using old message class name robot_core-srv:<BatchTransform-request> is deprecated: use robot_core-srv:BatchTransform-request instead.")))

(cl:ensure-generic-function 'ids-val :lambda-list '(m))
(cl:defmethod ids-val ((m <BatchTransform-request>))
  (roslisp-msg-protocol:msg-deprecation-warning "Using old-style slot reader robot_core-srv:ids-val is deprecated.  Use robot_core-srv:ids instead.")
  (ids m))

(cl:ensure-generic-function 'points-val :lambda-list '(m))
(cl:defmethod points-val ((m <BatchTransform-request>))
  (roslisp-msg-protocol:msg-deprecation-warning "Using old-style slot reader robot_core-srv:points-val is deprecated.  Use robot_core-srv:points instead.")
  (points m))
(cl:defmethod roslisp-msg-protocol:serialize ((msg <BatchTransform-request>) ostream)
  "Serializes a message object of type '<BatchTransform-request>"
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
)
(cl:defmethod roslisp-msg-protocol:deserialize ((msg <BatchTransform-request>) istream)
  "Deserializes a message object of type '<BatchTransform-request>"
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
  msg
)
(cl:defmethod roslisp-msg-protocol:ros-datatype ((msg (cl:eql '<BatchTransform-request>)))
  "Returns string type for a service object of type '<BatchTransform-request>"
  "robot_core/BatchTransformRequest")
(cl:defmethod roslisp-msg-protocol:ros-datatype ((msg (cl:eql 'BatchTransform-request)))
  "Returns string type for a service object of type 'BatchTransform-request"
  "robot_core/BatchTransformRequest")
(cl:defmethod roslisp-msg-protocol:md5sum ((type (cl:eql '<BatchTransform-request>)))
  "Returns md5sum for a message object of type '<BatchTransform-request>"
  "6021b6112a957556fbdf33fd163786a6")
(cl:defmethod roslisp-msg-protocol:md5sum ((type (cl:eql 'BatchTransform-request)))
  "Returns md5sum for a message object of type 'BatchTransform-request"
  "6021b6112a957556fbdf33fd163786a6")
(cl:defmethod roslisp-msg-protocol:message-definition ((type (cl:eql '<BatchTransform-request>)))
  "Returns full string definition for message of type '<BatchTransform-request>"
  (cl:format cl:nil "# === Request (Python 發送給 C++ 的請求) ===~%# 每個物體的唯一 ID (用來對應 shared_object 的 index)~%uint32[] ids~%~%# 相機座標列表 (對應上面的 ids)~%geometry_msgs/Point[] points~%~%~%================================================================================~%MSG: geometry_msgs/Point~%# This contains the position of a point in free space~%float64 x~%float64 y~%float64 z~%~%~%"))
(cl:defmethod roslisp-msg-protocol:message-definition ((type (cl:eql 'BatchTransform-request)))
  "Returns full string definition for message of type 'BatchTransform-request"
  (cl:format cl:nil "# === Request (Python 發送給 C++ 的請求) ===~%# 每個物體的唯一 ID (用來對應 shared_object 的 index)~%uint32[] ids~%~%# 相機座標列表 (對應上面的 ids)~%geometry_msgs/Point[] points~%~%~%================================================================================~%MSG: geometry_msgs/Point~%# This contains the position of a point in free space~%float64 x~%float64 y~%float64 z~%~%~%"))
(cl:defmethod roslisp-msg-protocol:serialization-length ((msg <BatchTransform-request>))
  (cl:+ 0
     4 (cl:reduce #'cl:+ (cl:slot-value msg 'ids) :key #'(cl:lambda (ele) (cl:declare (cl:ignorable ele)) (cl:+ 4)))
     4 (cl:reduce #'cl:+ (cl:slot-value msg 'points) :key #'(cl:lambda (ele) (cl:declare (cl:ignorable ele)) (cl:+ (roslisp-msg-protocol:serialization-length ele))))
))
(cl:defmethod roslisp-msg-protocol:ros-message-to-list ((msg <BatchTransform-request>))
  "Converts a ROS message object to a list"
  (cl:list 'BatchTransform-request
    (cl:cons ':ids (ids msg))
    (cl:cons ':points (points msg))
))
;//! \htmlinclude BatchTransform-response.msg.html

(cl:defclass <BatchTransform-response> (roslisp-msg-protocol:ros-message)
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

(cl:defclass BatchTransform-response (<BatchTransform-response>)
  ())

(cl:defmethod cl:initialize-instance :after ((m <BatchTransform-response>) cl:&rest args)
  (cl:declare (cl:ignorable args))
  (cl:unless (cl:typep m 'BatchTransform-response)
    (roslisp-msg-protocol:msg-deprecation-warning "using old message class name robot_core-srv:<BatchTransform-response> is deprecated: use robot_core-srv:BatchTransform-response instead.")))

(cl:ensure-generic-function 'ids-val :lambda-list '(m))
(cl:defmethod ids-val ((m <BatchTransform-response>))
  (roslisp-msg-protocol:msg-deprecation-warning "Using old-style slot reader robot_core-srv:ids-val is deprecated.  Use robot_core-srv:ids instead.")
  (ids m))

(cl:ensure-generic-function 'points-val :lambda-list '(m))
(cl:defmethod points-val ((m <BatchTransform-response>))
  (roslisp-msg-protocol:msg-deprecation-warning "Using old-style slot reader robot_core-srv:points-val is deprecated.  Use robot_core-srv:points instead.")
  (points m))

(cl:ensure-generic-function 'success-val :lambda-list '(m))
(cl:defmethod success-val ((m <BatchTransform-response>))
  (roslisp-msg-protocol:msg-deprecation-warning "Using old-style slot reader robot_core-srv:success-val is deprecated.  Use robot_core-srv:success instead.")
  (success m))
(cl:defmethod roslisp-msg-protocol:serialize ((msg <BatchTransform-response>) ostream)
  "Serializes a message object of type '<BatchTransform-response>"
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
(cl:defmethod roslisp-msg-protocol:deserialize ((msg <BatchTransform-response>) istream)
  "Deserializes a message object of type '<BatchTransform-response>"
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
(cl:defmethod roslisp-msg-protocol:ros-datatype ((msg (cl:eql '<BatchTransform-response>)))
  "Returns string type for a service object of type '<BatchTransform-response>"
  "robot_core/BatchTransformResponse")
(cl:defmethod roslisp-msg-protocol:ros-datatype ((msg (cl:eql 'BatchTransform-response)))
  "Returns string type for a service object of type 'BatchTransform-response"
  "robot_core/BatchTransformResponse")
(cl:defmethod roslisp-msg-protocol:md5sum ((type (cl:eql '<BatchTransform-response>)))
  "Returns md5sum for a message object of type '<BatchTransform-response>"
  "6021b6112a957556fbdf33fd163786a6")
(cl:defmethod roslisp-msg-protocol:md5sum ((type (cl:eql 'BatchTransform-response)))
  "Returns md5sum for a message object of type 'BatchTransform-response"
  "6021b6112a957556fbdf33fd163786a6")
(cl:defmethod roslisp-msg-protocol:message-definition ((type (cl:eql '<BatchTransform-response>)))
  "Returns full string definition for message of type '<BatchTransform-response>"
  (cl:format cl:nil "~%# === Response (C++ 回傳給 Python 的結果) ===~%# 回傳 ID 以確保順序正確 (通常跟請求的一樣)~%uint32[] ids~%~%# 轉換後的基座標列表~%geometry_msgs/Point[] points~%~%# 是否執行成功~%bool success~%~%================================================================================~%MSG: geometry_msgs/Point~%# This contains the position of a point in free space~%float64 x~%float64 y~%float64 z~%~%~%"))
(cl:defmethod roslisp-msg-protocol:message-definition ((type (cl:eql 'BatchTransform-response)))
  "Returns full string definition for message of type 'BatchTransform-response"
  (cl:format cl:nil "~%# === Response (C++ 回傳給 Python 的結果) ===~%# 回傳 ID 以確保順序正確 (通常跟請求的一樣)~%uint32[] ids~%~%# 轉換後的基座標列表~%geometry_msgs/Point[] points~%~%# 是否執行成功~%bool success~%~%================================================================================~%MSG: geometry_msgs/Point~%# This contains the position of a point in free space~%float64 x~%float64 y~%float64 z~%~%~%"))
(cl:defmethod roslisp-msg-protocol:serialization-length ((msg <BatchTransform-response>))
  (cl:+ 0
     4 (cl:reduce #'cl:+ (cl:slot-value msg 'ids) :key #'(cl:lambda (ele) (cl:declare (cl:ignorable ele)) (cl:+ 4)))
     4 (cl:reduce #'cl:+ (cl:slot-value msg 'points) :key #'(cl:lambda (ele) (cl:declare (cl:ignorable ele)) (cl:+ (roslisp-msg-protocol:serialization-length ele))))
     1
))
(cl:defmethod roslisp-msg-protocol:ros-message-to-list ((msg <BatchTransform-response>))
  "Converts a ROS message object to a list"
  (cl:list 'BatchTransform-response
    (cl:cons ':ids (ids msg))
    (cl:cons ':points (points msg))
    (cl:cons ':success (success msg))
))
(cl:defmethod roslisp-msg-protocol:service-request-type ((msg (cl:eql 'BatchTransform)))
  'BatchTransform-request)
(cl:defmethod roslisp-msg-protocol:service-response-type ((msg (cl:eql 'BatchTransform)))
  'BatchTransform-response)
(cl:defmethod roslisp-msg-protocol:ros-datatype ((msg (cl:eql 'BatchTransform)))
  "Returns string type for a service object of type '<BatchTransform>"
  "robot_core/BatchTransform")