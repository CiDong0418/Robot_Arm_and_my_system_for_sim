cmake_minimum_required(VERSION 3.5)
project(Project) # 請確保 package.xml 裡的 <name> 也是 Project

# 找到子项目
add_subdirectory(Manipulator)
add_subdirectory(MotorUnion)
add_subdirectory(Robot) 
add_subdirectory(Neck)

# 找到 Poco 和 Eigen
find_package(Poco REQUIRED Foundation Net)
find_package(Eigen3 REQUIRED)

find_package(catkin REQUIRED COMPONENTS
  roscpp
  std_msgs
)

# 链接 Poco 库
set(POCO_LIBS Poco::Net Poco::Foundation)

# 包含路徑 (加入 devel/include 讓 main.cpp 能找到 robot_core 的標頭檔)
include_directories(
  ${catkin_INCLUDE_DIRS}
  ${CATKIN_DEVEL_PREFIX}/include 
)

# 1. 定義執行檔
add_executable(ProjectNode main.cpp)

# ======================================================================
# 強制將編譯好的執行檔，搬移到 devel/lib/Project 資料夾下
# 如果沒有這段，rosrun 就會找不到 ProjectNode
# ======================================================================
set_target_properties(ProjectNode PROPERTIES
    RUNTIME_OUTPUT_DIRECTORY ${CATKIN_DEVEL_PREFIX}/lib/${PROJECT_NAME}
)

# 2. 設定依賴順序
# 確保在編譯 main.cpp 之前，robot_core 的 Service 訊息檔已經生成完畢
add_dependencies(ProjectNode robot_core_generate_messages_cpp)

# 3. 設定 Include 路徑
target_include_directories(ProjectNode PRIVATE ${CMAKE_SOURCE_DIR}/Robot)

# 4. 安裝規則 (選用，但建議保留)
install(TARGETS ProjectNode
  RUNTIME DESTINATION ${CATKIN_PACKAGE_BIN_DESTINATION}
)

# 5. 連結 Library
target_link_libraries(ProjectNode
  Manipulator   # 来自 src/Manipulator 子项目的库
  MotorUnion    # 来自 src/MotorUnion 子项目的库
  Robot         # 来自 src/Robot 子项目的库 (確保 Robot 的 CMakeLists 裡 add_library 是叫 Robot)
  Neck          # 来自 src/Neck 子项目的库
  ${POCO_LIBS}
  ${catkin_LIBRARIES}
)