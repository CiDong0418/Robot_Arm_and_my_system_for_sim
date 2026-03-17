#include "Neck.h"
#include <iostream>
#include <Eigen/Geometry>

using namespace Eigen;

Neck *Neck::inst_ = nullptr;

Neck *Neck::GetNeck()
{
	if (inst_ == nullptr)
		inst_ = new Neck();
	return inst_;
}

static const Eigen::Matrix<float,5,4> neck_table = (Eigen::Matrix<float,5,4>() <<
    0,     0,      45.25,     -227,
    0, -M_PI/2,    0,    0,
    0,    M_PI/2,   0,      -53,
    0,     0,      52.05,     0,
    0,     0,      0,        0
).finished();

Neck::Neck()
    : MotorUnion({20,21}, {"Mx106", "Mx106"}),
      DELAY_TIME_(1000)
{
	
	Start();  
    std::this_thread::sleep_for(std::chrono::milliseconds(DELAY_TIME_));
    UpdateAngle();
    // yaw = GetAngle(0)/ 180.0 * M_PI;
    // pitch = GetAngle(1)/ 180 * M_PI;

    std::cout << "================================================================================" << std::endl;
} 

void Neck::Start()
{
    SetAllMotorsTorqueEnable(true);
    SetAllMotorsOperatingMode(3); // 3 = angle mode
    SetAllMotorsVelocity(0);
    SetAllMotorsAccel(100); //1000
    std::cout << "Class constructed: Neck" << std::endl;
    std::cout << "================================================================================" << std::endl;
    // SetMotor_Operating_Mode(6, 5);
    // SetAllMotorsTorqueEnable(true); 
    
    
    
    
}

void Neck::Stop()
{
    SetAllMotorsTorqueEnable(false);
}
void Neck::UpdateAngle()
{
    std::this_thread::sleep_for(std::chrono::milliseconds(DELAY_TIME_));
    yaw = GetAngle(0)/180.0 * M_PI;
    pitch = GetAngle(1)/180.0 * M_PI;
    std::cout<<"Updated Neck Angles - Yaw: "<< yaw <<", Pitch: "<< pitch <<std::endl;

}

/**
 * @param idx 0:id20 1:id21
 * @param degangle - goal angle, in degree
 */

void Neck::SetMotorAngle(int idx, float degangle)
{
    SetMotor_Angle(idx, degangle);
    std::this_thread::sleep_for(std::chrono::milliseconds(DELAY_TIME_));
    UpdateAngle();
}

float Neck::GetAngle(int idx) const {
    std::cout << "angle " << idx + 20 << ": " << GetMotor_Angle(idx) << std::endl;
    return GetMotor_Angle(idx); // in degree
}

Matrix4f Neck::transformMatrix(float theta, float alpha, float a, float d) const {
    Matrix4f m;
    m << cos(theta), -cos(alpha)*sin(theta),  sin(alpha)*sin(theta), a*cos(theta),
         sin(theta),  cos(alpha)*cos(theta), -sin(alpha)*cos(theta), a*sin(theta),
                  0,             sin(alpha),            cos(alpha),           d,
                  0,                     0,                    0,           1;
    return m;
}


Matrix4f Neck::rotationMatrix(int axis, float theta) const {
    Matrix4f m = Matrix4f::Identity();
    float c = cos(theta), s = sin(theta);
    if (axis==0) { // x-axis
        m(1,1) = c; m(1,2) = -s;
        m(2,1) = s; m(2,2) = c;
    } else if(axis==1) { // y-axis
        m(0,0) = c; m(0,2) = s;
        m(2,0) = -s; m(2,2) = c;
    } else if(axis==2) { // z-axis
        m(0,0)= c; m(0,1) = -s;
        m(1,0)= s; m(1,1) = c;
    }
    return m;
}

void Neck::BaseToCameraTransform() {
    UpdateAngle();
    std::cout<<"yaw: "<< yaw <<std::endl;
    std::cout<<"pitch: "<< pitch <<std::endl;
        // std::cout<<"DH_table_: \n"<<DH_table_<<std::endl;
    Tb0_ = transformMatrix(neck_table(0,0)       , neck_table(0,1), neck_table(0,2), neck_table(0,3));
    T01_ = transformMatrix(neck_table(1,0) , neck_table(1,1), neck_table(1,2), neck_table(1,3));
    T1p_ = transformMatrix(neck_table(2,0)  + yaw, neck_table(2,1), neck_table(2,2), neck_table(2,3));
    Tpe_ = transformMatrix(neck_table(3,0)   , neck_table(3,1), neck_table(3,2), neck_table(3,3)); 
    Tee_ = transformMatrix(neck_table(4,0) + pitch  , neck_table(4,1), neck_table(4,2), neck_table(4,3));   
    
    // std::cout<<"Tb0_: \n"<<Tb0_<<std::endl;
    // std::cout<<"T01_: \n"<<T01_<<std::endl;
    // std::cout<<"T12_: \n"<<T12_<<std::endl;
    // std::cout<<"T23_: \n"<<T23_<<std::endl;
    Tb1_ = Tb0_*T01_;
    // std::cout<<"Tb1_: \n"<<Tb1_<<std::endl;
    Tbp_ = Tb1_*T1p_;
    Tbe_ = Tbp_*Tpe_;
    // std::cout<<"Tbc_: \n"<<Tbc_<<std::endl;   
}


Vector3f  Neck::GetBasePosition(float cx, float cy, float cz)
{
     // 1. 更新轉換矩陣
    BaseToCameraTransform() ;
    // 2. 建立相機座標系下的齊次座標點 (4x1)
    Vector4f camera_pos, pos_base;
    camera_pos << cx, cy, cz, 1.0f;  // 齊次座標需要加 1
    Tpitch_ = rotationMatrix(1, pitch);
    Tyaw_ = rotationMatrix(2, yaw);
    Vector4f camera_pos_transformed = Tyaw_ * Tpitch_ * camera_pos;
    // ✅ 正确：先声明，再用 << 赋值
    float hight=53*cos(pitch);
    float length = 52.05*cos(pitch)+ 53*sin(pitch);
    pos_base << camera_pos_transformed[0]+length+45.25, 
                camera_pos_transformed[1], 
                camera_pos_transformed[2]+hight+227,
                1.0f;


      // 4. 轉回 3D 座標
    Vector3f base_pos = pos_base.head<3>();
    // std::cout << "T1c_"<< pos_base << std::endl;
    // std::cout << "pos_p: " << pos_p.transpose() << std::endl;
    // std::cout <<"pos_21: " << pos_21.transpose() << std::endl;
    std::cout <<"camera_pos_transformed: " << camera_pos_transformed.transpose() << std::endl;
    // std::cout <<"pos_base: " << pos_base.transpose() << std::endl;
    std::cout << "Camera coords: [" << cx << ", " << cy << ", " << cz << "]" << std::endl;
    std::cout << "Base coords: [" << base_pos.x() << ", " 
              << base_pos.y() << ", " << base_pos.z() << "]" << std::endl;
    return base_pos;
}
