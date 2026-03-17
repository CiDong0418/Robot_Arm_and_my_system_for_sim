#ifndef ROBOT_H
#define ROBOT_H

#include <array>
#include <vector>
#include <string>
#include <cmath>
#include <utility>
#include <Eigen/Dense>
#include <Eigen/Geometry>
#include "../Manipulator/LeftArm.h"
#include "../Manipulator/RightArm.h"
#include "../Neck/Neck.h"
#include <eigen3/Eigen/Core>
#include <eigen3/Eigen/Dense>
#include <eigen3/Eigen/LU>
#include <vector>
#include <math.h>
#include <thread>
#include <ros/ros.h>
#include <std_msgs/String.h>
#include <nlohmann/json.hpp>


#include <geometry_msgs/Point.h>
#include <robot_core/BatchTransform.h> // 引入生成的 srv
#include <robot_core/ArmBatchTransform.h> // 引入生成的 srv
class Robot
{
public:
	static Robot *GetRobot();
	~Robot();
	
	
	LeftArm *leftArm;
	RightArm *rightArm;
	Neck *neck;
    Eigen::Vector3d Left_target_POS; // in world coord.
    Eigen::Vector3d Right_target_POS;// in world coord.

    ros::ServiceServer transform_server_;
    ros::ServiceServer transform_server_L;

    ros::Publisher action_state_pub;
    
    void initPublisher(ros::NodeHandle& nh);

    void Initialize();
    void synchronizeMove(double X, double Y, double Z, std::string pick_mode, double object_width);
    void posture_synchronizeMove(double ox_deg, double oy_deg, double oz_deg, double X, double Y, double Z, double object_width);
    
    void separateMove(double LX, double LY, double LZ, std::string Lpick_mode, int L_angle,
                      double RX, double RY, double RZ, std::string Rpick_mode, int R_angle);
    void posture_separateMove(double Lox_deg, double Loy_deg, double Loz_deg, double LX, double LY, double LZ,
                         double Rox_deg, double Roy_deg, double Roz_deg, double RX, double RY, double RZ);
    
    void singleArmMove(std::string arm, double X, double Y, double Z, std::string pick_mode, int angle);
    void posture_singleArmMove(std::string arm, double ox_deg, double oy_deg, double oz_deg, double X, double Y, double Z);

    void LookTable();
    // ROS callbacks
    void commandCallback(const std_msgs::String::ConstPtr& msg);
    void posture_commandCallback(const std_msgs::String::ConstPtr& msg);
    void pointCallback(const geometry_msgs::Point::ConstPtr& msg);
    void VoiceCommandCallback(const std_msgs::String::ConstPtr& msg);
    // void LeftCameraCallback(const geometry_msgs::Point::ConstPtr& msg);
    // void RightCameraCallback(const geometry_msgs::Point::ConstPtr& msg);
    void Action_Done_Callback(string msg_s) ;
    // 參數型別要改成 robot_core::
    bool batchTransformCallback(robot_core::BatchTransform::Request &req,
                            robot_core::BatchTransform::Response &res);

    bool ArmCameraTransform(robot_core::ArmBatchTransform::Request &req,
                            robot_core::ArmBatchTransform::Response &res);

    void Neckcontrol(float yaw_deg, float pitch_deg);
    Eigen::Vector3d camera_to_world_transform(double cx, double cy, double cz, int camera_id);
    
    void closeGripper(std::string arm);
    void openGripper(std::string arm);
    void GripperController(std::string arm, float angle);
    void refineGripperPosition(std::string arm, float adjustment);
    void refineGripper_thread(std::string arm , float adjustment, double angle);
    void linear_gripper_control(std::string arm);
    void waitForArm(std::string arm);

private:
	static Robot *inst_;
    ros::Publisher base_point_pub_;
    ros::Publisher voice_command_pub_;
    
	Robot();
    Eigen::Vector3d  camera_to_base_transform(double cx, double cy, double cz, int camera_id);
};
#endif // ROBOT_H