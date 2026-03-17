#ifndef ARMINFO_H
#define ARMINFO_H

#include <array>
#include <vector>
#include <string>
#include <cmath>
#include <utility>
#include <Eigen/Dense>
#include <Eigen/Geometry>
#include "../../MotorUnion/MotorUnion.h"

#include <Poco/Net/SocketStream.h>
#include <Poco/Net/StreamSocket.h>
#include <Poco/Net/SocketAddress.h>
#include <eigen3/Eigen/Core>
#include <eigen3/Eigen/Dense>
#include <eigen3/Eigen/LU>
#include <vector>
#include <math.h>
#include <thread>
// Assume MotorUnion is defined elsewhere and provides motor control APIs
class MotorUnion;

class ArmInfo : public MotorUnion {
public:
    // Constructor
    ArmInfo(const Eigen::Matrix<double,7,4>& DH_table,
            const std::vector<unsigned char>& IDArray,
            const std::vector<std::string>& MotorModelArrayList);
    ~ArmInfo(){};         
    Eigen::Vector3d current_position_;
    Eigen::Vector3d current_orientation_;
    std::string pick_type;
    double angle_shift;
    // motor control functions
    void Start();
    void Stop();
    void checkConnected();
    void Stop_all_motors();
    void SetIndexVelocity(int idx, double vel);
    void SetArmVelocity(double v0, double v1, double v2,
                        double v3, double v4, double v5);
    void openGripper();
    void closeGripper();
    void Grippercontrol(float close_angle);
    bool stepMoveJ(const Eigen::Matrix<double,6,1>& target_joints,
                   double max_speed_rad,
                   double acceleration_factor);
    // check robot state
    std::pair<Eigen::Vector3d, std::pair<Eigen::Vector3d, std::string>>
    checkPositionWorkspace(const Eigen::Vector3d& pos_in,
                           const Eigen::Vector3d& ori_in,
                           const std::string& type,
                           const std::string& arm);
        
    Eigen::Vector3d computeRetreatAlongZ(double retreat_distance_mm);

    std::pair<Eigen::Vector3d, std::string>
    getPickTypePose(const std::string& arm,
                    const std::string& ptype,
                    double angle = 0.0);
    void checkMotorLimit();

    void update();
    void update_pick_mode(std::string mode);
    bool check_pick_mode_change(std::string mode);
    void update_angle_shift(double angle);
    // transform matrices
    Eigen::Matrix4d transformMatrix(double theta,
                                    double alpha,
                                    double a,
                                    double d) const;

    Eigen::Matrix4d rotationMatrix(int axis,
                                   double theta) const;

    Eigen::Vector4d EEtransformTobasePosition(
        const Eigen::Vector3d& ee_pos);

    Eigen::Vector4d transformToBasePosition(
        const Eigen::Vector3d& pos_world) const;
    
    Eigen::Vector4d transformToWorldPosition(
        const Eigen::Vector3d& pos_base) const;

    void forwardKinematics();
    void jacobian();
    // double wrapToPi(double angle);

    
    // setting and getting functions
    void setWorldToBaseTransform(double alpha,
                                 double d);

    void setTargetOrientation(double ox_deg,
                              double oy_deg,
                              double oz_deg);

    void setTargetPosition(double x,
                           double y,
                           double z);

    void setDeltaAngle(const Eigen::Matrix<double,6,1>& delta);
    void setMotorAngle(int idx, double angle);
    Eigen::VectorXd solveDLS(const Eigen::MatrixXd& J, const Eigen::VectorXd& xdot); // 0.1
    
    void setJointVelocity(const Eigen::VectorXd& linear_vel);
    void setJointIdxVelocity(double vel, int idx);
    void setErrorIntegral(const Eigen::Matrix<double,6,1>& integral);
    void setStallCounter(int count);

    // get information functions
    Eigen::Matrix<double,6,1> getJointVelocity() const;
    Eigen::Vector3d getCurrentPosition() const;
    Eigen::Vector3d getTargetPosition() const;
    Eigen::Vector3d getCurrentOrientationInDegree() const;
    // Eigen::Vector4d getCurrentOrientationInQuaternion() const;
    double getIdxJointVelocity(int Idx) const;
    Eigen::Matrix<double,6,1> getMotorAngle() const;
    double pro_radpersec2scale_;
    const double END_EFFECTOR_LENGTH_;
    const int DELAY_TIME_;
    const unsigned char FIRST_HAND_ID_;

    Eigen::Vector4d object_in_base_position;
    Eigen::Quaterniond current_orientation_q4;
    // void deltaAngleCallback(const std_msgs::Float64MultiArray::ConstPtr& msg);
    Eigen::Matrix<double,6,1> motor_angles_;
private:
    // DH parameters
    Eigen::Matrix<double,7,4> DH_table_;

    // Motor scaling and parameters
    
    

    // Transforms
    Eigen::Matrix4d Tb0_, T01_, T12_, T23_, T34_, T45_, T5E_;
    Eigen::Matrix4d Tb1_, Tb2_, Tb3_, Tb4_, Tb5_, TbE_;
    Eigen::Matrix4d T02_, T03_, T04_, T05_, T0E_;

    Eigen::Vector3d P01, P02, P03, P04, P05, P0E, PbE_;
    Eigen::Matrix4d world_to_base_, base_to_world_; // camera_to_ee_
    double distance_to_base_;

    // Joint & end-effector state
    
    Eigen::Vector3d target_position_; // in base coord.
    Eigen::Vector3d target_orientation_;

    Eigen::Matrix<double,6,1> delta_angle_;
    
    Eigen::Matrix<double,6,1> joint_velocity_;
    Eigen::Matrix<double,6,1> error_integral_;
    double max_integral_;
    
    int stall_counter_;
    bool is_out_of_limit_;
    bool is_working_;

    // Kinematic results
    double ox_, oy_, oz_;
    Eigen::Matrix<double,6,6> jacobian_matrix_;
    Eigen::Matrix<double,6,6> inverse_jacobian_;
    double damping_factor = 0.1;
};

#endif // ARMINFO_H
