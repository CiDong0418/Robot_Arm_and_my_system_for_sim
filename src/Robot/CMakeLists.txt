cmake_minimum_required(VERSION 3.5)

# 【修改 1】這裡必須跟 package.xml 一樣，改成 robot_core
project(robot_core)

# 尋找依賴套件
find_package(catkin REQUIRED COMPONENTS
  roscpp
  std_msgs
  geometry_msgs      
  message_generation 
)

add_service_files(
  FILES
  BatchTransform.srv
  ArmBatchTransform.srv
)

generate_messages(
  DEPENDENCIES
  std_msgs
  geometry_msgs
)

catkin_package(
  CATKIN_DEPENDS roscpp rospy std_msgs geometry_msgs message_runtime
)

find_package(OpenCV REQUIRED)
find_package(Eigen3 REQUIRED)

include_directories(
  ${CMAKE_CURRENT_SOURCE_DIR}
  ${catkin_INCLUDE_DIRS}
  ${OpenCV_INCLUDE_DIRS}
  ${EIGEN3_INCLUDE_DIRS}
)

# 建立 Robot library
add_library(Robot SHARED Robot.cpp)

# 【修改 2：非常重要！】
# 這行是告訴編譯器：在編譯 Robot.cpp 之前，先生成 robot_core 的 header 檔
# 如果少了這行，就會報 "BatchTransform.h not found"
add_dependencies(Robot ${${PROJECT_NAME}_EXPORTED_TARGETS} ${catkin_EXPORTED_TARGETS})

# 連結函式庫
target_link_libraries(Robot
  Manipulator
  ${catkin_LIBRARIES}           
  ${OpenCV_LIBS}
)

target_include_directories(Robot PUBLIC
  ${CMAKE_CURRENT_SOURCE_DIR}
  ${catkin_INCLUDE_DIRS}
  ${OpenCV_INCLUDE_DIRS}
)