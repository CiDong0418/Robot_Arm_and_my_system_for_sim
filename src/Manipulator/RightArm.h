#ifndef RIGHTARM_H
#define RIGHTARM_H

#include <Eigen/Dense>
#include <Eigen/Geometry>
#include <memory>
#include <chrono>
#include <thread>
#include <iostream>
#include <string>
#include <cmath>
#include <algorithm>
#include <Poco/Net/SocketAddress.h>
#include <Poco/Net/StreamSocket.h>
#include <Poco/Net/SocketStream.h>
#include <Poco/Exception.h>
#include <time.h>
#include "./ArmInfo/ArmInfo.h"


class RightArm : public ArmInfo {
public:
    static RightArm *GetRightArm();
    ~RightArm() { inst_ = nullptr; };
    

    
    // Eigen::Matrix4d transformMatrix(double theta, const float &alpha, const float &a, const float &d);
    // Eigen::Matrix<float, 4, 4> GetTransformMatrix(const float &theta, const float &alpha, const float &a, const float &d);
    // Eigen::Matrix<float, 3, 3> GetRotationMatrix(const int &axis_index, const float &theta);
    // float GetCurrentPosition(int index);
    // float GetCurrentOrientation(int index);

    bool stepIK(double ox_deg, double oy_deg, double oz_deg,
                double px, double py, double pz, double acceleration_factor);
    
    bool step_move(double ox_deg, double oy_deg, double oz_deg, 
                   double px, double py, double pz, double acceleration_factor);
    
    void trajectory_planning(double ox, double oy, double oz, 
                           double px, double py, double pz, bool mode_change);
    
    void Trajectory_Planning(double ox_deg, double oy_deg, double oz_deg, 
                           double X, double Y, double Z, 
                           std::string pick_mode = "side");
    void Trajectory_Planning_NoCheck(double ox_deg, double oy_deg, double oz_deg, 
                           double X, double Y, double Z);
    
    // bool stepMoveJ(const Eigen::Matrix<double,6,1>& target_joints, double max_speed_rad, double acceleration_factor);
    void Angle_adjust(double ox_deg, double oy_deg, double oz_deg, bool mode_change);
                         
    void mode_controll(double X, double Y, double Z, std::string pick_mode, double angle);
    // Utility functions
    Eigen::Vector3d getOrientationMode(const std::string& mode, double shift = 0.0);
    void setInitialPose();
    void setpositionPose(double x, double y, double z);
    void updateRobotPose();
    void getArmInformation() const;
    bool GetWorkingState();
    
    // Helper functions
    static int Sign(float x);

    void PneumaticOn();
    void PneumaticOff();
    bool first_iteration_ = true;
    Eigen::Vector3d last_error_pos_ = Eigen::Vector3d::Zero();
    Eigen::Vector3d last_current_pos_ = Eigen::Vector3d::Zero();
    double velocity_history_[5];
    int velocity_idx_ = 0;
    int convergence_counter_ = 0;
    void testing();
private:
    RightArm();
    static RightArm *inst_;
    // Quaternion operations
    Eigen::Quaterniond quatConjugate(const Eigen::Quaterniond& q);
    Eigen::Quaterniond quatMul(const Eigen::Quaterniond& a, const Eigen::Quaterniond& b);

    // Constants and configuration
    // const double pro_radpersec2scale_ = 60.0 / (2 * M_PI) / 0.01; // Motor scaling factor: 60.0 / (2 * M_PI) / 0.01
    // const double END_EFFECTOR_LENGTH_ = 210.0; // End effector length: 210 mm
    // const int DELAY_TIME_ = 5;             // Control loop delay: 5 ms
    // const unsigned char FIRST_HAND_ID_ = 0;          // First hand motor ID: 0

    // DH parameters and offsets
    // Eigen::Matrix<double,7,4> left_arm_DH_;      // DH parameter table (7x4)
    const double gripper_offset_ = 100.0;      // Gripper offset: 100.0 mm
    const double object_offset_ = 100.0;       // Object offset: 100.0 mm
    const double z_offset_ = 50.0;            // Z-axis offset: 50.0 mm


    // Current state variables
    Eigen::Vector3d right_world_pos_;      // Current world position
    Eigen::Vector3d right_orientation_deg_; // Current orientation in degrees
    Eigen::Vector3d last_position_;       // Last recorded position for stall detection
    
    // Control parameters
    const double vel_gain_linear_ = 1.2;           // Linear velocity gain: 1.2
    const double vel_gain_angular_ = 1.2;   // Angular velocity gain: 1.2
    const double ki_gain_ = 0.1;            // Integral gain: 0.1
    const double angular_threshold_ = M_PI/180.0;  // Angular convergence threshold: π/180 radians (1°)
    const double linear_threshold_ = 1.0;   // Linear convergence threshold: 1.0 mm
    int stop_counter_ = 0;        // Stall detection counter (triggers at >50)

    // State flags and counters
    bool is_out_of_limit_;    // Joint limit flag
    bool is_working_;         // Working state flag
    bool Finished;            // Motion completion flag
    static Eigen::Matrix<double,6,1> prev_qdot;
 
};

#endif // LEFTARM_H