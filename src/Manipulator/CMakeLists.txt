cmake_minimum_required(VERSION 3.5)
project(Manipulator)

add_subdirectory(ArmInfo)

# Build shared library for Manipulator, include GripperController
add_library(Manipulator SHARED
  LeftArm.cpp
  RightArm.cpp
)


find_package(Poco REQUIRED Foundation Net) 
set(POCO_LIBS Poco::Net Poco::Foundation)
find_package(Eigen3 REQUIRED)
include_directories(${EIGEN3_INCLUDE_DIRS})
# Add include path for Dynamixel SDK
include_directories(
  ${CMAKE_CURRENT_SOURCE_DIR}
  ../MotorUnion/Motor/dynamixel/dynamixel_sdk
)

target_include_directories(Manipulator PUBLIC
  ${CMAKE_CURRENT_SOURCE_DIR}      # 导出 LeftArm.h
  ${EIGEN3_INCLUDE_DIRS}
)



target_link_libraries(Manipulator ArmInfo ${POCO_LIBS})
