
#include <ros/ros.h>
#include <std_msgs/String.h>
#include <nlohmann/json.hpp>
#include "Robot.h"
#include <geometry_msgs/Point.h>

using json = nlohmann::json;


int main(int argc, char **argv)
{
    ros::init(argc, argv, "command_subscriber"); // Initialize ROS node
    ros::NodeHandle nh;

    // 創建 Robot 實例
    Robot* robot = Robot::GetRobot();
    std::this_thread::sleep_for(std::chrono::milliseconds(1000));
    // robot->LookTable();
   
    // === 初始化 Publisher（新增） ===
    robot->initPublisher(nh);

    ros::Subscriber headCamera_sub = nh.subscribe("/camera/head", 10, 
                                            &Robot::pointCallback, robot);
    // ros::Subscriber camera_left_sub = nh.subscribe("/camera/left", 10, 
    //                                         &Robot::LeftCameraCallback, robot);
    // ros::Subscriber camera_right_sub = nh.subscribe("/camera/right", 10, 
    //                                         &Robot::RightCameraCallback, robot);
                                            

    ros::Subscriber sub = nh.subscribe("robot_command", 10, &Robot::commandCallback, robot);
    ros::Subscriber posture_sub = nh.subscribe("posture_command", 10, &Robot::posture_commandCallback, robot);
    
    ROS_INFO("Command Subscriber started");
    ros::spin();
    
    return 0;
}
