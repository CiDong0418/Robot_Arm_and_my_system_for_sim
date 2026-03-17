cmake_minimum_required(VERSION 3.5)
project(ArmInfo)

find_package(OpenCV REQUIRED)
include_directories(${OpenCV_INCLUDE_DIRS})

find_package(Eigen3 REQUIRED)
include_directories(${EIGEN3_INCLUDE_DIRS})
# # 添加 MotorUnion 头文件路径
# include_directories(
 
#   ${CMAKE_CURRENT_SOURCE_DIR}/../../MotorUnion  # ← 添加此行
# )

# # Add include path for Dynamixel SDK
# include_directories(
#   ${CMAKE_CURRENT_SOURCE_DIR}
#   /../../MotorUnion/Motor/dynamixel/dynamixel_sdk
# )




add_library(ArmInfo SHARED ArmInfo.cpp)
target_link_libraries(ArmInfo MotorUnion ${OpenCV_LIBS})
target_include_directories(ArmInfo PUBLIC ${OpenCV_INCLUDE_DIRS})