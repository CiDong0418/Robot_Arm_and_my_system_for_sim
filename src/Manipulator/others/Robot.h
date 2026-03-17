#ifndef ROBOT_H
#define ROBOT_H

#include <array>
#include <vector>
#include <cmath>
#include "ArmInfo.h"
#include <Eigen/Dense>
#include <Eigen/Geometry>

class Robot {
public:
    Robot();

    // Workspace check & orientation adjustment
    std::pair<Eigen::Vector3d, std::pair<Eigen::Vector3d, std::string>>
    checkPositionWorkspace(const Eigen::Vector3d& pos_in,
                           const Eigen::Vector3d& ori_in,
                           const std::string& type,
                           const std::string& arm);

    // Pick-type pose
    std::pair<Eigen::Vector3d, std::string>
    getPickTypePose(const std::string& arm,
                    const std::string& ptype,
                    double angle = 0.0);

    // Quaternion utils
    Eigen::Quaterniond quatConjugate(const Eigen::Quaterniond& q);
    Eigen::Quaterniond quatMul(const Eigen::Quaterniond& a, const Eigen::Quaterniond& b);

    // Single-step IK update
    bool stepIK(double ox_deg, double oy_deg, double oz_deg,
                double px, double py, double pz,
                const std::string& mode,
                ArmInfo& single_arm);

    // Orientation by mode
    Eigen::Vector3d getOrientationMode(const std::string& mode, double shift = 0.0);

    void setInitialPose(const std::array<double,6>& angles);
    void updateRobotPose();
    void getArmInformation() const;

private:
    Eigen::Matrix<double,7,4> left_arm_DH_;
    Eigen::Matrix<double,7,4> right_arm_DH_;

    ArmInfo left_arm_;
    ArmInfo right_arm_;

    double gripper_offset_;
    double object_offset_;
    double z_offset_;

    std::array<double,6> initial_angle_;

    Eigen::Vector3d left_world_pos_;
    Eigen::Vector3d right_world_pos_;
    Eigen::Vector3d left_orientation_deg_;
    Eigen::Vector3d right_orientation_deg_;

    // Gains & thresholds
    double vel_gain_;
    double vel_gain_angular_;
    double ki_gain_;
    double angular_threshold_;
    double linear_threshold_;
    int stop_counter_;

    Eigen::Quaterniond q_target_;
    Eigen::Quaterniond q_current_;
    Eigen::Matrix<double,6,1> xdot_;
    Eigen::Vector3d last_position_;
};

#endif // ROBOT_H
