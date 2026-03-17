cmake_minimum_required(VERSION 3.5)
project(Neck)

find_package(OpenCV REQUIRED)
find_package(catkin REQUIRED COMPONENTS
  roscpp
  std_msgs
  message_generation  # 加入這行以生成 service
)


include_directories(${OpenCV_INCLUDE_DIRS})

find_package(Eigen3 REQUIRED)
include_directories(${EIGEN3_INCLUDE_DIRS})

include_directories(
  ${catkin_INCLUDE_DIRS}      # ROS 頭文件
)



add_library(Neck SHARED Neck.cpp)
target_link_libraries(Neck 
    MotorUnion 
    ${OpenCV_LIBS}
    ${catkin_LIBRARIES}         # ROS 庫
    )
target_include_directories(Neck PUBLIC ${OpenCV_INCLUDE_DIRS})