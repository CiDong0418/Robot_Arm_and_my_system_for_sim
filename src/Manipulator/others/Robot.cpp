#include "Robot.h"
#include <iostream>

using namespace Eigen;
using std::cout;
using std::endl;

Robot::Robot()
  : left_arm_DH_{}, right_arm_DH_{},
    left_arm_(left_arm_DH_, 0, 6),
    right_arm_(right_arm_DH_, 6, 12),
    gripper_offset_(100.0),
    object_offset_(100.0),
    z_offset_(50.0),
    initial_angle_{0, -M_PI/2, 0, 0, 0, 0},
    left_world_pos_(Vector3d::Zero()),
    right_world_pos_(Vector3d::Zero()),
    left_orientation_deg_(Vector3d::Zero()),
    right_orientation_deg_(Vector3d::Zero()),
    vel_gain_(1.5),
    vel_gain_angular_(1.2),
    ki_gain_(0.1),
    angular_threshold_(M_PI/180.0),
    linear_threshold_(1.0),
    stop_counter_(0)
{
    // Fill DH tables
    left_arm_DH_ << 0,     0,      0,    233,
                    0, -M_PI/2,    0,      0,
                    0,     0, 265.7,      0,
                    0, -M_PI/2,   30,      0,
                    0,  M_PI/2,    0,    264,
                    0, -M_PI/2,    0,      0,
                    0,     0,      0, 235.27;
    right_arm_DH_ = left_arm_DH_;

    left_arm_.setWorldToBaseTransform(-M_PI/2, 0.0);
    right_arm_.setWorldToBaseTransform( M_PI/2, 0.0);
}

std::pair<Vector3d, std::pair<Vector3d, std::string>>
Robot::checkPositionWorkspace(const Vector3d& pos_in,
                              const Vector3d& ori_in,
                              const std::string& type,
                              const std::string& arm)
{
    Vector3d pos = pos_in;
    Vector3d ori = ori_in;
    bool change_pos = false, change_ori = false;

    const double max_z = 400, min_z = -330;
    const double min_x = 200, max_x = 700;
    const double max_y = 760, min_y = -760;

    // Bound checks
    if (pos.z() > max_z) { pos.z() = max_z; change_pos = true; }
    if (pos.z() < min_z) { pos.z() = min_z; change_pos = true; }
    if (pos.x() < min_x) { pos.x() = min_x; change_pos = true; }
    if (pos.x() > max_x) { pos.x() = max_x; change_pos = true; }
    if (pos.y() > max_y) { pos.y() = max_y; change_pos = true; }
    if (pos.y() < min_y) { pos.y() = min_y; change_pos = true; }

    // Orientation adjustments
    if (pos.z() > 170 && pos.z() <= max_z && type=="down") {
        auto p = getPickTypePose(arm,"side",90);
        ori = p.first; change_ori = true;
    }
    // In-table region
    if (std::abs(pos.x())<530 && std::abs(pos.x())>200 &&
        pos.y() < 260 && pos.y()>-260)
    {
        if (type=="forward" && pos.x()<400) {
            auto p = getPickTypePose(arm,"side");
            ori = p.first; change_ori = true;
        }
    }
    // Side regions
    if (std::abs(pos.x())<530 && std::abs(pos.x())>200 &&
        std::abs(pos.y())>=360)
    {
        if (type!="forward") {
            auto p = getPickTypePose(arm,"forward");
            ori = p.first; change_ori = true;
        }
    }
    // Far forward
    if (std::abs(pos.x())>=530 && std::abs(pos.x())<=700 &&
        std::abs(pos.y())>=360)
    {
        if (type!="forward") {
            auto p = getPickTypePose(arm,"forward");
            ori = p.first; change_ori = true;
        }
    }

    if (change_pos) cout<<"Warning: position out of workspace!!!!!!"<<endl;
    if (change_ori) cout<<"Warning: orientation changed!!!!!!!!"<<endl;

    return {pos,{ori,type}};
}

std::pair<Vector3d,std::string>
Robot::getPickTypePose(const std::string& arm,
                       const std::string& ptype,
                       double angle)
{
    Vector3d ori(0,0,0);
    std::string outType = ptype;

    if (arm=="left") {
        if (ptype=="side") {
            ori = Vector3d(-180,0,0);
            if (angle>=90) {
                double sup = 180-angle;
                ori.y() = sup;
                if (angle==90) outType="forward";
            } else ori.y() = -angle;
        }
        else if(ptype=="down"){
            ori=Vector3d(-90,0,-90);
            if(angle>90) ori.z()=-(180-angle);
            else ori.z()=angle;
        }
        else if(ptype=="forward"){
            ori=Vector3d(-180,90,0);
        }
    }
    else if(arm=="right"){
        if(ptype=="side"){
            ori=Vector3d(0,180,0);
            if(angle>90) ori.y()=-angle;
            else ori.y()=(180-angle);
        }
        else if(ptype=="down"){
            ori=Vector3d(90,0,-90);
            if(angle>90) ori.z()=angle;
            else ori.z()=-(180-angle);
        }
        else if(ptype=="forward"){
            ori=Vector3d(0,90,0);
        }
    } else {
        cout<<"Unknown arm"<<endl;
    }
    return {ori,outType};
}

Quaterniond Robot::quatConjugate(const Quaterniond& q) {
    return Quaterniond(q.w(), -q.x(), -q.y(), -q.z());
}

Quaterniond Robot::quatMul(const Quaterniond& a, const Quaterniond& b) {
    return a * b;
}

bool Robot::stepIK(double ox_deg, double oy_deg, double oz_deg,
                   double px, double py, double pz,
                   const std::string& mode,
                   ArmInfo& single_arm)
{
    Vector3d pos(px,py,pz);
    Vector3d ori_deg(ox_deg,oy_deg,oz_deg);

    single_arm.setTargetOrientation(ori_deg[0],ori_deg[1],ori_deg[2]);
    single_arm.setTargetPosition(pos[0],pos[1],pos[2]);

    updateRobotPose();

    // Compute quaternions
    Quaterniond q_target = AngleAxisd(ori_deg[0]*M_PI/180,"X"_xaxis()) *
                           AngleAxisd(ori_deg[1]*M_PI/180,"Y"_yaxis()) *
                           AngleAxisd(ori_deg[2]*M_PI/180,"Z"_zaxis());
    Quaterniond q_current = AngleAxisd(left_orientation_deg_[0]*M_PI/180,"X"_xaxis()) *
                            AngleAxisd(left_orientation_deg_[1]*M_PI/180,"Y"_yaxis()) *
                            AngleAxisd(left_orientation_deg_[2]*M_PI/180,"Z"_zaxis());

    // Error quaternion
    if(q_current.dot(q_target)<0) q_target.coeffs() *=-1;
    Quaterniond q_err = quatMul(q_target, quatConjugate(q_current));

    double qw = std::clamp(q_err.w(), -1.0,1.0);
    double angle = 2*acos(qw);
    Vector3d axis;
    double s = sqrt(1 - qw*qw);
    if(s<1e-8) axis=Vector3d::Zero();
    else axis = q_err.vec()/s;
    if(angle>M_PI){ angle=2*M_PI-angle; axis=-axis; }
    Vector3d error_ang_vec = axis*angle;
    double angular_error_norm = error_ang_vec.norm();

    Vector3d error_pos = single_arm.getTargetPosition() - single_arm.getCurrentPosition();
    double linear_error_norm = error_pos.norm();

    if(linear_error_norm<linear_threshold_ && angular_error_norm<angular_threshold_) {
        single_arm.setErrorIntegral(VectorXd::Zero(6));
        return true;
    }

    VectorXd w = vel_gain_angular_ * error_ang_vec;
    VectorXd v = vel_gain_ * error_pos;
    if(linear_error_norm>100) v *=1.5;
    else if(linear_error_norm<10) v *=0.7;

    xdot_.head<3>() = w;
    xdot_.tail<3>() = v;

    single_arm.setJointVelocity(xdot_);
    single_arm.checkMotorLimit();

    // Deadzone
    for(int i=0;i<6;++i)
        if(std::abs(single_arm.getJointVelocity()[i])<5e-4)
            single_arm.setJointIdxVelocity(0.0,i);

    // Stall detection
    Vector3d curr = single_arm.getCurrentPosition();
    if((last_position_-curr).norm()<0.1) {
        if(++stop_counter_>50) {
            stop_counter_=0;
            return true;
        }
    } else stop_counter_ = 0;

    last_position_ = curr;
    return false;
}







Vector3d Robot::getOrientationMode(const std::string& mode, double shift) {
    if(mode=="top") {
        Vector3d ori(-90,0,0);
        ori.z() = (shift>90 ? 180-shift : -shift);
        return ori;
    }
    if(mode=="side") {
        Vector3d ori(-180,0,0);
        ori.y() = (shift>90 ? 180-shift : -shift);
        return ori;
    }
    if(mode=="forward") {
        return Vector3d(-180,90,0);
    }
    cout<<"Unknown mode, use side"<<endl;
    return Vector3d(-180,0,0);
}

void Robot::setInitialPose(const std::array<double,6>& angles) {
    initial_angle_ = angles;
}

void Robot::updateRobotPose() {
    left_arm_.update();
    right_arm_.update();
    left_world_pos_ = left_arm_.transformToWorldPosition(left_arm_.getCurrentPosition());
    right_world_pos_ = right_arm_.transformToWorldPosition(right_arm_.getCurrentPosition());
    left_orientation_deg_ = left_arm_.getCurrentOrientationInDegree();
    right_orientation_deg_ = right_arm_.getCurrentOrientationInDegree();
}

void Robot::getArmInformation() const {
    cout<<"==================================="<<endl;
    cout<<"Current left world Position = "<<left_world_pos_.transpose()<<endl;
    cout<<"Current left Orientation(deg) = "<<left_orientation_deg_.transpose()<<endl;
    cout<<"-----------------------------------"<<endl;
    cout<<"Current right world  Position = "<<right_world_pos_.transpose()<<endl;
    cout<<"Current right Orientation(deg) = "<<right_orientation_deg_.transpose()<<endl;
    cout<<"==================================="<<endl;
}
