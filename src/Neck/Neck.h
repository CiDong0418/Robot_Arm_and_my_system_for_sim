#ifndef NECK_H
#define NECK_H

#include <array>
#include <vector>
#include <string>
#include <cmath>
#include <utility>
#include <Eigen/Dense>
#include <Eigen/Geometry>
#include "../MotorUnion/MotorUnion.h"

#include <eigen3/Eigen/Core>
#include <eigen3/Eigen/Dense>
#include <eigen3/Eigen/LU>
#include <vector>
#include <math.h>
#include <thread>
// Assume MotorUnion is defined elsewhere and provides motor control APIs
class MotorUnion;

class Neck : public MotorUnion {

public:
    // Constructor
    static Neck *GetNeck();
    ~Neck() { Stop();inst_ = nullptr; };
    
    void SetMotorAngle(int idx, float degangle);
    float GetAngle(int idx) const;
    float yaw;
    float pitch;
    Eigen::Vector3f  GetBasePosition(float cx, float cy, float cz);

private:
    static Neck *inst_;
    const int DELAY_TIME_;
    void UpdateAngle();
    Neck();
    void Start();
    void Stop();

    Eigen::Matrix4f transformMatrix(float theta, float alpha, float a, float d) const;
    void BaseToCameraTransform();
    Eigen::Matrix4f rotationMatrix(int axis, float theta) const ;

    Eigen::Matrix4f Tb0_, T01_, T1p_, Tpe_, Tee_, Tpitch_, Tyaw_;
    Eigen::Matrix4f Tb1_, Tbp_, Tbe_;
};

#endif // NECK_H
