cmake_minimum_required(VERSION 3.0.2)
project(task_manager)

## 尋找依賴套件
find_package(catkin REQUIRED COMPONENTS
  rospy
  std_msgs
)

## 宣告這是一個 catkin 套件
catkin_package()

## 指定 Python 執行檔安裝位置 (這步很重要，讓 rosrun 找得到)
catkin_install_python(PROGRAMS
  scripts/main_input_node.py
  scripts/high_level_node.py
  scripts/subtask_node.py
  DESTINATION ${CATKIN_PACKAGE_BIN_DESTINATION}
)

## 安裝 launch 檔案
install(DIRECTORY launch/
  DESTINATION ${CATKIN_PACKAGE_SHARE_DESTINATION}/launch
)