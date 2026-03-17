
(cl:in-package :asdf)

(defsystem "robot_core-srv"
  :depends-on (:roslisp-msg-protocol :roslisp-utils :geometry_msgs-msg
)
  :components ((:file "_package")
    (:file "ArmBatchTransform" :depends-on ("_package_ArmBatchTransform"))
    (:file "_package_ArmBatchTransform" :depends-on ("_package"))
    (:file "BatchTransform" :depends-on ("_package_BatchTransform"))
    (:file "_package_BatchTransform" :depends-on ("_package"))
  ))