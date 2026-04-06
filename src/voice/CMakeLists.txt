cmake_minimum_required(VERSION 3.0.2)
project(voice)

find_package(catkin REQUIRED COMPONENTS
  rospy
  std_msgs
)

catkin_package()

catkin_install_python(PROGRAMS
  scripts/voice_node.py
  scripts/assistant_reply_tts_node.py
  scripts/assistant_reply_tts_node_host.py
  DESTINATION ${CATKIN_PACKAGE_BIN_DESTINATION}
)
