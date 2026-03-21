cmake_minimum_required(VERSION 3.0.2)
project(image)

find_package(catkin REQUIRED COMPONENTS
  rospy
  std_msgs
  geometry_msgs
  sensor_msgs
  cv_bridge
  message_filters
  message_generation
)

add_service_files(
  FILES
  GetObjectXYZ.srv
)

generate_messages(
  DEPENDENCIES
  std_msgs
  geometry_msgs
)

catkin_package(
  CATKIN_DEPENDS
  rospy
  std_msgs
  geometry_msgs
  sensor_msgs
  cv_bridge
  message_filters
  message_runtime
)

## 安裝 ROS 節點腳本（讓 rosrun 找得到）
catkin_install_python(PROGRAMS
  scripts/head_xyz_detection.py
  scripts/right_arm_xyz_detection.py
  scripts/head_xyz_test_client.py
  scripts/head_xyz_service_server.py
  DESTINATION ${CATKIN_PACKAGE_BIN_DESTINATION}
)
