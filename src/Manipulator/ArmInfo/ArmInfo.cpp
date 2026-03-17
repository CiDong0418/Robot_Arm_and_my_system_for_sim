#include "ArmInfo.h"
#include <iostream>
#include <Eigen/Geometry>

using namespace Eigen;
// ArmInfo *ArmInfo::inst_ = nullptr;
// ArmInfo *ArmInfo::GetArmInfo()
// {
// 	if (inst_ == nullptr)
// 		inst_ = new ArmInfo();
// 	return inst_;
// }

ArmInfo::ArmInfo(const Matrix<double,7,4>& DH_table,  const vector<unsigned char> &IDArray, const vector<string> &MotorModelArrayList)
   
    : MotorUnion(IDArray, MotorModelArrayList), 
      pro_radpersec2scale_(60.0 / (2 * M_PI) / 0.01), // Goal Velocity 0.01 [rev/min]
      END_EFFECTOR_LENGTH_(210),
      DELAY_TIME_(100),
      FIRST_HAND_ID_(0),
      DH_table_(DH_table),
      current_position_(Vector3d::Zero()),
      current_orientation_(Vector3d::Zero()),
      target_position_(Vector3d::Zero()),
      delta_angle_(Matrix<double,6,1>::Zero()),
      motor_angles_(Matrix<double,6,1>::Zero()),
      joint_velocity_(Matrix<double,6,1>::Zero()),
      max_integral_(10.0),
      error_integral_(Matrix<double,6,1>::Zero()),
      angle_shift(0.0),
      stall_counter_(0),
      is_out_of_limit_(false),
      pick_type("side")

{
    // camera_to_ee_ = rotationMatrix(2, M_PI).inverse();
    is_working_ = false;
	is_out_of_limit_ = false;
	Start();
    
    // update();
    
} 
/* motor control functions
Start : set all motors to velocity mode, enable torque, set velocity and acceleration to 0
Stop : disable torque for all motors
SetArmVelocity : set velocity for all 6 motors
openGripper : open the gripper (motor ID 31 or 32)
closeGripper : close the gripper (motor ID 31 or 32)
*/
// 改SetAllMotorsAccel ,1000->1500, kp->0.1 don't stop delay, 

void ArmInfo::Start()
{
    SetAllMotorsTorqueEnable(true);
    SetAllMotorsOperatingMode(1); // 1 = velocity mode
    SetAllMotorsVelocity(0);
    SetAllMotorsAccel(1500); //1000
    printf("All motors set to velocity mode and enabled.\n");
    SetMotor_Operating_Mode(6, 5);
    SetAllMotorsTorqueEnable(true); 
    
    
}

void ArmInfo::Stop()
{
    SetAllMotorsTorqueEnable(false);
}
void ArmInfo::checkConnected()
{
    
    for (int i = 0; i < 7; i++)
    {
        if (!GetMotor_Connected(i))
        {
            std::cerr << "Motor ID " <<  i << " is not connected!" << std::endl;
            Stop();
            // Stop_all_motors();
            
            
        }
    }
}
void ArmInfo::Stop_all_motors()
{
    SetAllMotorsVelocity(0);
}
void ArmInfo::SetIndexVelocity(int idx, double vel)
{
    SetMotor_Velocity(FIRST_HAND_ID_ + idx, vel * pro_radpersec2scale_);
}



void ArmInfo::SetArmVelocity(double v0, double v1, double v2, double v3, double v4, double v5)
{
    SetMotor_Velocity(FIRST_HAND_ID_ + 0, v0 * pro_radpersec2scale_);
    SetMotor_Velocity(FIRST_HAND_ID_ + 1, v1 * pro_radpersec2scale_);
    SetMotor_Velocity(FIRST_HAND_ID_ + 2, v2 * pro_radpersec2scale_);
    SetMotor_Velocity(FIRST_HAND_ID_ + 3, v3 * pro_radpersec2scale_);
    SetMotor_Velocity(FIRST_HAND_ID_ + 4, v4 * pro_radpersec2scale_);
    SetMotor_Velocity(FIRST_HAND_ID_ + 5, v5 * pro_radpersec2scale_);
}

void ArmInfo::openGripper() {
    SetMotor_Angle(6, 5); // array index 6 = ID 32
    std::cout << "\t[INFO] Gripper Open Success!" << std::endl;
    WaitMotorArrival(4);
}

void ArmInfo::closeGripper() {
    SetMotor_Angle(6, 700);//700
	std::cout << "\t[INFO] Gripper Hold Success!" << std::endl;
    WaitMotorArrival(4);
}
void ArmInfo::Grippercontrol(float close_angle) {

    SetMotor_Angle(6, close_angle);//700
    std::cout << "\t[INFO] Gripper Hold Success!" << std::endl;
    WaitMotorArrival(4);
}



bool ArmInfo::stepMoveJ(const Eigen::Matrix<double,6,1>& target_joints, double max_speed_rad, double acceleration_factor) {
    
    // 1. [替換] 取得當前關節角度 (rad)
    Eigen::Matrix<double,6,1> current_joints = getMotorAngle(); 
    
    // 2. 計算誤差向量
    Eigen::Matrix<double,6,1> diff = target_joints - current_joints;
    
    // 3. 找出差距最大的那個關節 (Leading Axis)
    double max_diff = diff.cwiseAbs().maxCoeff();
    
    // 4. 設定收斂條件 (例如所有軸誤差都在 0.03 rad 以內)
    if (max_diff < 0.03) { 
        // SetArmVelocity(Eigen::Matrix<double,6,1>::Zero()); 
        SetArmVelocity(0.0, 0.0, 0.0, 0.0, 0.0, 0.0);// 停機
        return true; // 到達目標
    }

    // 5. 計算同步速度 (Synchronized Velocity)
    // 邏輯：所有軸的速度 = (該軸距離 / 最大距離) * 全域速度 * 加速度因子
    Eigen::Matrix<double,6,1> cmd_vel = (diff / max_diff) * max_speed_rad * acceleration_factor;

    SetArmVelocity(cmd_vel(0)*pro_radpersec2scale_,
                       cmd_vel(1)*pro_radpersec2scale_,
                        cmd_vel(2)*pro_radpersec2scale_,
                        cmd_vel(3)*pro_radpersec2scale_,
                        cmd_vel(4)*pro_radpersec2scale_,
                        cmd_vel(5)*pro_radpersec2scale_);
    
    return false; // 還沒到
}

/* check robot state
checkPositionWorkspace : check if the target position is within the workspace, adjust if necessary
getPickTypePose : get the target orientation based on pick type and arm side
checkMotorLimit : check if any motor angle is out of limit
update : update forward kinematics and Jacobian
*/



/*
* @param  Vector3d& pos_in - target position in world frame
* @param  Vector3d& ori_in - target orientation in world frame
* @param  std::string& type - type of movement (e.g., "forward", "down", "side")
* @param  std::string& arm - which arm is being used (e.g., "left", "right")
* @retval std::pair<Vector3d, std::pair<Vector3d, std::string>> - adjusted position, orientation, and type
*/
std::pair<Vector3d, std::pair<Vector3d, std::string>>
ArmInfo::checkPositionWorkspace(const Vector3d& pos_in,
                              const Vector3d& ori_in,
                              const std::string& type,
                              const std::string& arm)
{
    Vector3d pos = pos_in;
    Vector3d ori = ori_in;
    std::string type_out = type;
    bool change_pos = false, change_ori = false;

    const double max_z = 400, min_z = -350;
    const double min_x = 200, max_x = 700;
    const double max_y = 760, min_y = -760;

    // Bound checks:position adjustments
    if (pos.z() > max_z) { pos.z() = max_z; change_pos = true; }
    if (pos.z() < -330 && type=="side") { pos.z() = -330; change_pos = true; }
    if (pos.z() < min_z) { pos.z() = min_z; change_pos = true; }
    if (pos.x() < min_x) { pos.x() = min_x; change_pos = true; }
    if (pos.x() > max_x) { pos.x() = max_x; change_pos = true; }
    if (pos.y() > max_y) { pos.y() = max_y; change_pos = true; }
    if (pos.y() < min_y) { pos.y() = min_y; change_pos = true; }

    // Orientation adjustments(too high)
    if (pos.z() > 170 && pos.z() <= max_z && type=="down") {
        auto p = getPickTypePose(arm,"side",90);
        ori = p.first; change_ori = true;
        type_out="side";
    }
    // In-table region
    if (std::abs(pos.x())<530 && std::abs(pos.x())> 200 &&
        pos.y() < 260 && pos.y()>-260)
    {
        if (type=="forward" && pos.x()<400) {
            auto p = getPickTypePose(arm,"side",0);
            ori = p.first; change_ori = true;
            type_out="side";
        }
        if (type== "side"){
            if (pos.z()< -308){
                pos.z() = -307; 
                change_pos = true;
            }
        }
    }
    // Side regions
    if (std::abs(pos.x())<530 && std::abs(pos.x())>200 &&
        std::abs(pos.y())>=360)
    {
        if (type!="forward") {
            auto p = getPickTypePose(arm,"forward",0);
            ori = p.first; change_ori = true;
            type_out="forward";
        }
    }
    // Far forward
    if (std::abs(pos.x())>=530 && std::abs(pos.x())<=700 &&
        std::abs(pos.y())>=360)
    {
        if (type!="forward") {
            auto p = getPickTypePose(arm,"forward",0);
            ori = p.first; change_ori = true;
            type_out="forward";
        }
    }

    if (change_pos) cout<<"Warning: position out of workspace!!!!!!"<<endl;
    if (change_ori) cout<<"Warning: orientation changed!!!!!!!!"<<endl;
    update_pick_mode(type_out);
    return std::make_pair(pos, std::make_pair(ori, type_out));
}
/*
computeRetreatAlongZ: Compute a new position by retreating along the Z-axis of the end-effector frame.
@param retreat_distance_mm: Distance to retreat in millimeters.
@retval Vector3d: New position in the base frame after retreating.
*/
Vector3d ArmInfo::computeRetreatAlongZ(double retreat_distance_mm) {
    // 從 TbE_ 提取旋轉矩陣的第三列（Z軸方向向量）
    Vector3d z_axis_in_base = TbE_.block<3,1>(0,2);
    
    // 沿Z軸後退（負號表示後退方向）
    Vector3d global_retreat = -z_axis_in_base * retreat_distance_mm;
    
    // 計算新位置
    Vector3d new_position = current_position_ + global_retreat;
    
    std::cout << "Z-axis direction (base frame): " << z_axis_in_base.transpose() << std::endl;
    std::cout << "Retreat vector: " << global_retreat.transpose() << std::endl;
    std::cout << "New position after retreat: " << new_position.transpose() << std::endl;
    
    return new_position;
}
bool ArmInfo:: check_pick_mode_change(std::string mode) {
    if (mode != pick_type && (mode == "down" || pick_type == "down")) {
        std::cout << "\t[INFO] Pick mode changed from " << pick_type << " to " << mode << std::endl;
        return true;
    }else {
        return false;
    }
}

void ArmInfo::update_pick_mode(std::string mode) {
    pick_type = mode;
}
void ArmInfo::update_angle_shift(double angle) {
    angle_shift = angle; //deg
}
void ArmInfo::update() {
    for (int i = 0; i < 6; ++i){
        // std::cout<<"i: "<<i<<std::endl;
        // std::cout<<GetMotor_PresentAngle(FIRST_HAND_ID_ + i)<<std::endl;
        
        setMotorAngle(i, GetMotor_PresentAngle(FIRST_HAND_ID_ + i) * Angle2Rad);
    }
    
    setDeltaAngle(motor_angles_);
    // forwardKinematics();
    // jacobian();
}


/*
* @param std::string& arm - which arm is being used (e.g., "left", "right")
* @param std::string& ptype - pick type (e.g., "side", "down", "forward")
* @param double angle - supplementary angle for certain pick types (deg)
* @retval std::pair<Vector3d,std::string> - target orientation and possibly adjusted pick type
*/
std::pair<Vector3d,std::string>
ArmInfo::getPickTypePose(const std::string& arm,
                       const std::string& ptype,
                       double angle)
{
    Vector3d ori(-180,0,0);
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
            ori=Vector3d(-95,0,-90); //-93,0,-90
            // if(angle>90 || angle == 90) ori.z()=-(180-angle);
            // else ori.z()=angle;

            ori.z()=angle;
         
        }
        else if(ptype=="forward"){
            ori=Vector3d(-180,90,0);
        }
        else if(ptype=="side_forward"){
            // ori=Vector3d(0,-180,-90);
            ori = Vector3d(-180,0,-90);
            
        }
        else if (ptype=="side_reversal"){
           
            ori = Vector3d(-180, 40, 0);
            
            if (angle<=180 && angle >=0)  ori.z() = angle;
            
        }
        else if (ptype == "side_down"){
            ori = Vector3d(-180, 0, 90);
            if (angle>=90) {
                double sup = 180-angle;
                ori.y() = sup;
                
            } else ori.y() = -angle;

        }
    }
    else if(arm=="right"){
        if(ptype=="side"){
            ori=Vector3d(0,180,0);
            if(angle>90) ori.y()=-angle;
            else ori.y()=(180-angle);
        }
        else if(ptype=="down"){
            ori=Vector3d(95, 0, -180); // 90,0,-90
            // if (angle< 0) ori.z() = (180 + angle);
            // else if (angle>90) ori.z()=angle;
            // else ori.z()=-(180-angle);
            if (angle > 0 || angle == 0) ori.z() = -(180-angle);
            else ori.z() = (180 + angle);
        }
        
        else if(ptype=="forward"){
            ori=Vector3d(0,110,0);
        }
        else if(ptype=="side_forward"){
            ori=Vector3d(0,180,90);
            
        }
        else if (ptype=="side_reversal"){
            
            ori = Vector3d(0,140, 0);
            
            if (angle<=180 && angle >=0)  ori.z() = -angle;
            
        }
        else if (ptype == "side_down"){
           
            ori=Vector3d(0,180,-90);
            if(angle>90) ori.y()=-angle;
            else ori.y()=(180-angle);
            
        }
    } else {
        cout<<"Unknown arm"<<endl;
    }
    update_angle_shift(angle);
    return {ori,outType};
}

void ArmInfo::checkMotorLimit() {
    double max_speed = 0;
    int max_index = 0;
    // for(int i=0;i<6;++i) {
    //     if (std::abs(joint_velocity_(i)) > max_speed) {
    //         max_speed = std::max(max_speed, std::abs(joint_velocity_(i)));
    //         max_index = i;
    //     }
    // }
    max_speed = joint_velocity_.cwiseAbs().maxCoeff(&max_index);
    if (max_speed >= (M_PI  / 60)){
        joint_velocity_ *= (M_PI  / 60) / max_speed;
        std::cout<<"Speed too high, limit to 3 deg/s"<<std::endl;
    }
            
    
    
}







/* transform matrices
transformMatrix : compute the transformation matrix from DH parameters
rotationMatrix : compute rotation matrix around a specified axis
transformToEndEffectorPosition : transform a position from camera frame to end-effector frame
transformToBasePosition : transform a position from world frame to base frame
transformToWorldPosition : transform a position from base frame to world frame
wrapToPi : wrap an angle to the range [-pi, pi]
forwardKinematics : compute the forward kinematics to get current position and orientation
jacobian : compute the Jacobian matrix and its inverse



*/


Matrix4d ArmInfo::transformMatrix(double theta, double alpha, double a, double d) const {
    Matrix4d m;
    m << cos(theta), -cos(alpha)*sin(theta),  sin(alpha)*sin(theta), a*cos(theta),
         sin(theta),  cos(alpha)*cos(theta), -sin(alpha)*cos(theta), a*sin(theta),
                  0,             sin(alpha),            cos(alpha),           d,
                  0,                     0,                    0,           1;
    return m;
}

Matrix4d ArmInfo::rotationMatrix(int axis, double theta) const {
    Matrix4d m = Matrix4d::Identity();
    double c = cos(theta), s = sin(theta);
    if (axis==0) {
        m(1,1) = c; m(1,2) = -s;
        m(2,1) = s; m(2,2) = c;
    } else if(axis==1) {
        m(0,0) = c; m(0,2) = s;
        m(2,0) = -s; m(2,2) = c;
    } else if(axis==2) {
        m(0,0)= c; m(0,1) = -s;
        m(1,0)= s; m(1,1) = c;
    }
    return m;
}

Vector4d ArmInfo::EEtransformTobasePosition(const Vector3d& ee_pos) {
    std::cout << "Transforming EE position to base position: (" << ee_pos.x() << ", " << ee_pos.y() << ", " << ee_pos.z() << ")" << std::endl;
    Vector4d ee_coord{ee_pos.x(), ee_pos.y(), ee_pos.z(), 1};

    object_in_base_position = TbE_ * ee_coord;
    std::cout << "Resulting base position: (" << object_in_base_position.x() << ", " << object_in_base_position.y() << ", " << object_in_base_position.z() << ")" << std::endl;
    return object_in_base_position;
}
Vector4d ArmInfo::transformToBasePosition(const Vector3d& pos_world) const {
    Vector4d w{pos_world.x(), pos_world.y()-distance_to_base_, pos_world.z(),1};
    return world_to_base_ * w;
}

Vector4d ArmInfo::transformToWorldPosition(const Vector3d& pos_base) const {
    Vector4d b{pos_base.x(), pos_base.y(), pos_base.z(),1};
    Vector4d w = base_to_world_ * b;
    w.y() += distance_to_base_;
    return w;
}



// 歸一化到 [-π, π]
double wrapToPi(double a) {
    a = std::fmod(a + M_PI, 2*M_PI);
    if (a < 0) a += 2*M_PI;
    return a - M_PI;
}

void ArmInfo::forwardKinematics() {
    Eigen::Matrix<double,6,1> tt;
    
    // tt << 1.76327/180*M_PI, -20.8473/180*M_PI, 1.37917/180*M_PI, -73.7916/180*M_PI, -14.4716/180*M_PI, 39.8/180*M_PI;
    // tt << 0, -M_PI/2, 0,  0, 0,  0;
    // tt << 0.98943, -0.557161, 0.0187393, -1.28869, 0.638063, 0.69464;
    // tt << 0, -M_PI/3, 0,  M_PI*2/3, -M_PI/3,  M_PI/3;
    // setDeltaAngle(tt);
    std::cout<<"delta_angle_: "<<delta_angle_.transpose()<<std::endl;
        // std::cout<<"DH_table_: \n"<<DH_table_<<std::endl;
    Tb0_ = transformMatrix(DH_table_(0,0)                , DH_table_(0,1), DH_table_(0,2), DH_table_(0,3));
    T01_ = transformMatrix(DH_table_(1,0)+delta_angle_(0), DH_table_(1,1), DH_table_(1,2), DH_table_(1,3));
    T12_ = transformMatrix(DH_table_(2,0)+delta_angle_(1), DH_table_(2,1), DH_table_(2,2), DH_table_(2,3));
    T23_ = transformMatrix(DH_table_(3,0)+delta_angle_(2), DH_table_(3,1), DH_table_(3,2), DH_table_(3,3));
    T34_ = transformMatrix(DH_table_(4,0)+delta_angle_(3), DH_table_(4,1), DH_table_(4,2), DH_table_(4,3));
    T45_ = transformMatrix(DH_table_(5,0)+delta_angle_(4), DH_table_(5,1), DH_table_(5,2), DH_table_(5,3));
    T5E_ = transformMatrix(DH_table_(6,0)+delta_angle_(5), DH_table_(6,1), DH_table_(6,2), DH_table_(6,3));
    // std::cout<<"Tb0_: \n"<<Tb0_<<std::endl;
    // std::cout<<"T01_: \n"<<T01_<<std::endl;
    // std::cout<<"T12_: \n"<<T12_<<std::endl;
    // std::cout<<"T23_: \n"<<T23_<<std::endl;
    Tb1_ = Tb0_*T01_;
    // std::cout<<"Tb1_: \n"<<Tb1_<<std::endl;
    Tb2_ = Tb1_*T12_;
    // std::cout<<"Tb2_: \n"<<Tb2_<<std::endl;
    Tb3_ = Tb2_*T23_;
    Tb4_ = Tb3_*T34_;
    Tb5_ = Tb4_*T45_;
    TbE_ = Tb5_*T5E_;
    // std::cout<<"TbE_: \n"<<TbE_<<std::endl;
    T02_ = T01_*T12_;
    T03_ = T02_*T23_;
    T04_ = T03_*T34_;
    T05_ = T04_*T45_;
    T0E_ = T05_*T5E_;

    // Positions
    P01 = T01_.block<3,1>(0,3);
    P02 = T02_.block<3,1>(0,3);
    P03 = T03_.block<3,1>(0,3);
    P04 = T04_.block<3,1>(0,3);
    P05 = T05_.block<3,1>(0,3);
    P0E = T0E_.block<3,1>(0,3);

    PbE_ = TbE_.block<3,1>(0,3);
    // std::cout<<"PbE_: "<<PbE_.transpose()<<std::endl;
    current_position_(0) = PbE_(0);
    current_position_(1) = PbE_(1);
    current_position_(2) = PbE_(2);
    std::cout<<"Current Position: "<<current_position_.transpose()<<std::endl;
    // Orientation
    Matrix3d R_matrix = TbE_.block<3,3>(0,0);
    // std::cout<<"R_matrix: \n"<<R_matrix<<std::endl;
    
    double ox, oy, oz;
    
    // 萬向鎖檢測：當 |R[0,2]| ≈ 1 時發生（即 |sin(oy)| ≈ 1）
    const double threshold = 0.99999;

    if (std::abs(R_matrix(0,2)) > threshold) {
        // 萬向鎖情況
        oz_ = 0.0;  // 設定為0（與scipy一致）
        
        // 從 R[1,1] 和 R[1,0] 提取 ox
        // 當 oy = π/2: R[1,1] = cos(ox), R[1,0] = sin(ox)
        // 當 oy = -π/2: R[1,1] = cos(ox), R[1,0] = -sin(ox)
        ox_ = std::atan2(R_matrix(1,0), R_matrix(1,1));
        
        // 確定 oy 的符號
        // 當 oy ≈ π/2 時，R[0,2] ≈ 1
        // 當 oy ≈ -π/2 時，R[0,2] ≈ -1
        if (R_matrix(0,2) > 0) {
            oy_ = M_PI / 2.0;
        } else {
            oy_ = -M_PI / 2.0;
        }
        
    } else {
        // 正常情況：提取XYZ外旋歐拉角
        // R = Rx(ox) @ Ry(oy) @ Rz(oz)
        oy_ = std::asin(R_matrix(0,2));              // asin(R[0,2])
        ox_ = std::atan2(-R_matrix(1,2), R_matrix(2,2));  // atan2(-R[1,2], R[2,2])
        oz_ = std::atan2(-R_matrix(0,1), R_matrix(0,0));  // atan2(-R[0,1], R[0,0])
    }

    // 歸一化到 [-π, π]
    ox_ = wrapToPi(ox_);
    oy_ = wrapToPi(oy_);
    oz_ = wrapToPi(oz_);
    


    std::cout << "Current Orientation (rad): " << Vector3d(ox_, oy_, oz_).transpose() << std::endl;

   
    // Quaterniond q(Rmat);
    // Vector3d euler = q.toRotationMatrix().eulerAngles(0,1,2);
    // ox_ = wrapToPi(euler.x());
    // oy_ = wrapToPi(euler.y());
    // oz_ = wrapToPi(euler.z());
    current_orientation_ = Vector3d(ox_,oy_,oz_);
}

void ArmInfo::jacobian() {
    // Compute columns
    std::array<Vector3d,6> Z = {
        Vector3d(0,0,1),
        T01_.block<3,1>(0,2), // 起始於第 0 行第 2 列、大小為 3 行 1 列的區塊
        T02_.block<3,1>(0,2),
        T03_.block<3,1>(0,2),
        T04_.block<3,1>(0,2),
        T05_.block<3,1>(0,2)
    };
    std::array<Vector3d,6> P = {
        Vector3d(0,0,0),
        P01,
        P02,
        P03,
        P04,
        P05
    };
    Vector3d Pende = P0E;

    for(int i=0;i<6;++i){
        Vector3d Jv = Z[i].cross(Pende - P[i]);
        jacobian_matrix_.block<3,1>(0,i) = Z[i];
        jacobian_matrix_.block<3,1>(3,i) = Jv;
        
    }
    inverse_jacobian_ = jacobian_matrix_.completeOrthogonalDecomposition().pseudoInverse();
    // std::cout<<"Jacobian Matrix:\n"<<jacobian_matrix_<<std::endl;
}

/* setting and getting functions
setWorldToBaseTransform : set the transformation from world frame to base frame
setTargetOrientation : set the target orientation in degrees
setTargetPosition : set the target position in mm
setDeltaAngle : set the delta angles for each joint
setMotorAngle : set the motor angle for a specific joint
setJointVelocity : set the joint velocities
setJointIdxVelocity : set the velocity for a specific joint
setErrorIntegral : set the error integral for PID control
*/

void ArmInfo::setWorldToBaseTransform(double alpha, double d) {
    distance_to_base_ = d;
    world_to_base_ = transformMatrix(0, alpha, 0, 0).inverse();
    base_to_world_  = transformMatrix(0, alpha, 0, 0);
}

void ArmInfo::setTargetOrientation(double ox_deg, double oy_deg, double oz_deg) {
    target_orientation_ = Vector3d(ox_deg/180*M_PI, oy_deg/180*M_PI, oz_deg/180*M_PI);
}

void ArmInfo::setTargetPosition(double x, double y, double z) {
    target_position_ = Vector3d(x,y,z);
}




void ArmInfo::setDeltaAngle(const Matrix<double,6,1>& delta_rad) {

    delta_angle_ = delta_rad;
}

void ArmInfo::setMotorAngle(int idx, double angle_rad) {
    motor_angles_(idx) = angle_rad;
}

Eigen::VectorXd ArmInfo::solveDLS(const Eigen::MatrixXd& J, const Eigen::VectorXd& xdot) {
    // std::cout << "=== DLS Solver (PyBullet Style) ===" << std::endl;
    // std::cout << "Desired velocity (xdot): " << xdot.transpose() << std::endl;
    
    double lambda = 0.08;  // 使用與 PyBullet 相同的阻尼係數
    // std::cout << "Jacobian Matrix (J):\n" << J << std::endl;
    // *** (J^T * J + λ²*I)^(-1) * J^T ***
    Eigen::MatrixXd JtJ = J.transpose() * J;  // 6x6 矩陣
    // std::cout << "J^T * J:\n" << JtJ << std::endl;
    Eigen::MatrixXd damped = JtJ + std::pow(lambda, 2) * Eigen::MatrixXd::Identity(J.cols(), J.cols());
    
    // std::cout << "Damped Matrix:\n" << damped << std::endl;
    // 使用與 NumPy 類似的完整求逆
    Eigen::MatrixXd damped_inv = damped.inverse();
    
    // std::cout << "Damped Inverse Matrix:\n" << damped_inv << std::endl;
    Eigen::VectorXd q_dot = damped_inv * J.transpose() * xdot;
    
    // std::cout << "Joint Velocity Result: " << q_dot.transpose() << std::endl;
    
    return q_dot;
}


void ArmInfo::setJointVelocity(const Eigen::VectorXd& linear_vel) 
{
    // std::cout << "Set linear velocity to: " << linear_vel.transpose() << std::endl;
    // std::cout << "Inverse jacobian (for debug):\n" << inverse_jacobian_ << std::endl;
    joint_velocity_ = solveDLS(jacobian_matrix_, linear_vel);
    // joint_velocity_ = jacobian_matrix_.lu().solve(linear_vel);  
    // 需要根據你的系統添加 joint_velocity 用法，例如給控制器
    std::cout << "Joint velocity: " << joint_velocity_.transpose() << std::endl;
}

void ArmInfo::setJointIdxVelocity(double vel, int idx) {
    joint_velocity_(idx) = vel;
}

void ArmInfo::setErrorIntegral(const Matrix<double,6,1>& integral) {
    error_integral_ = integral;
}

void ArmInfo::setStallCounter(int count) {
    stall_counter_ = count;
}







/* get information functions 
getJointVelocity : get the current joint velocities
getCurrentPosition : get the current end-effector position
getTargetPosition : get the target end-effector position
getCurrentOrientationInDegree : get the current end-effector orientation in degrees

getMotorAngle : get the current motor angles
*/
Matrix<double,6,1> ArmInfo::getJointVelocity() const {
    return joint_velocity_;
}
double ArmInfo::getIdxJointVelocity(int Idx) const {
    return joint_velocity_(Idx);
}

Vector3d ArmInfo::getCurrentPosition() const {
    return current_position_;
}

Vector3d ArmInfo::getTargetPosition() const {
    return target_position_;
}

Vector3d ArmInfo::getCurrentOrientationInDegree() const {
    return current_orientation_ * 180.0/M_PI;
}
Eigen::Matrix<double,6,1> ArmInfo::getMotorAngle() const {
    return motor_angles_; //rad
}

// Eigen::Vector4d ArmInfo::getCurrentOrientationInQuaternion() const {
//     return current_orientation_q4.coeffs();
// }

