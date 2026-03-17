#include "Robot.h"
#include <iostream>
#include <Eigen/Geometry>
#include <string>
#include <algorithm>
#include <cctype>
#include <thread>
#include <chrono>
#include <string>
#include <vector>
#include <cctype>



using namespace Eigen;
using json = nlohmann::json;

Robot *Robot::inst_ = nullptr;

Robot *Robot::GetRobot()
{
    if (inst_ == nullptr)
        inst_ = new Robot();
    return inst_;
}




Robot::Robot()
{
    rightArm = RightArm::GetRightArm();
    leftArm = LeftArm::GetLeftArm();
    neck = Neck::GetNeck();
    Left_target_POS = Vector3d(420, 120, -130);
    Right_target_POS = Vector3d(420, -120, -130);
    std::cout << "Class constructed: Robot" << std::endl;
    std::cout << "================================================================================" << std::endl;
    std::this_thread::sleep_for(std::chrono::seconds(5));
    Initialize();
}

Robot::~Robot()
{
    delete rightArm;
    delete leftArm;
    inst_ = nullptr;
}

void Robot::Initialize()
{
    std::cout << "程式開始\n";
    std::this_thread::sleep_for(std::chrono::seconds(3));

    // 建立兩個執行緒，分別執行左右手臂的初始化
    std::thread rightThread([&]() {
        rightArm->setInitialPose();
    });
    std::thread leftThread([&]() {
        leftArm->setInitialPose();
    });
    std::thread neck1Thread([&]() {
        neck->SetMotorAngle(0, 0.0);
        
    });
    std::thread neck2Thread([&]() {
        neck->SetMotorAngle(1, 0.0);
        // neck->SetMotorAngle(1, 0.0);
        
    });
    //  std::thread rightAngleThread([&]() {
    //     rightArm->Angle_adjust();
    // });

    // 等待兩個執行緒都完成
    rightThread.join();
    leftThread.join();
    neck1Thread.join();
    neck2Thread.join();
    // rightAngleThread.join();
    std::cout << "兩手臂初始化完成\n";  
    
}

void Robot::synchronizeMove(double X, double Y, double Z, std::string pick_mode, double object_width)
{
    std::thread rightThread([this, X, Y, Z, pick_mode, object_width]() {
        rightArm->mode_controll( X,  Y-object_width/2,  Z, pick_mode, 0);
    });
    std::thread leftThread([this, X, Y, Z, pick_mode, object_width]() {
        leftArm->mode_controll( X,  Y+object_width/2,  Z, pick_mode, 0);
    });
    // 等待兩個執行緒都完成
    rightThread.join();
    leftThread.join();
   
}



void Robot::posture_synchronizeMove(double ox_deg, double oy_deg, double oz_deg, double X, double Y, double Z, double object_width)
{
    std::thread rightThread([this, ox_deg, oy_deg, oz_deg, X, Y, Z, object_width]() {
        rightArm->Trajectory_Planning_NoCheck(ox_deg, oy_deg, oz_deg, X, Y - object_width / 2, Z);
    });
    std::thread leftThread([this, ox_deg, oy_deg, oz_deg, X, Y, Z, object_width]() {
        leftArm->Trajectory_Planning_NoCheck(ox_deg, oy_deg, oz_deg, X, Y + object_width / 2, Z);
    });
    // 等待兩個執行緒都完成
    rightThread.join();
    leftThread.join();
   
}




void Robot::separateMove(double LX, double LY, double LZ, std::string Lpick_mode, int L_angle,
                         double RX, double RY, double RZ, std::string Rpick_mode, int R_angle)
{
    std::thread rightThread([this, RX, RY, RZ, Rpick_mode, R_angle]() {
        rightArm->mode_controll( RX,  RY,  RZ, Rpick_mode, R_angle);
    });
    std::thread leftThread([this, LX, LY, LZ, Lpick_mode, L_angle]() {
        leftArm->mode_controll( LX,  LY,  LZ, Lpick_mode, L_angle);
    });
    // 等待兩個執行緒都完成
    rightThread.join();
    leftThread.join();

    Action_Done_Callback("Done");
}

void Robot::posture_separateMove(double Lox_deg, double Loy_deg, double Loz_deg, double LX, double LY, double LZ,
                         double Rox_deg, double Roy_deg, double Roz_deg, double RX, double RY, double RZ)
{
    std::thread rightThread([this, Rox_deg, Roy_deg, Roz_deg, RX, RY , RZ]() {
        rightArm->Trajectory_Planning_NoCheck(Rox_deg, Roy_deg, Roz_deg, RX, RY , RZ);
    });
    std::thread leftThread([this, Lox_deg, Loy_deg, Loz_deg, LX, LY, LZ]() {
        leftArm->Trajectory_Planning_NoCheck(Lox_deg, Loy_deg, Loz_deg,LX , LY , LZ);
    });
    // 等待兩個執行緒都完成
    rightThread.join();
    leftThread.join();

    Action_Done_Callback("Done");
}


void Robot::singleArmMove(std::string arm, double X, double Y, double Z, std::string pick_mode, int angle)
{
    if (arm == "left") {
        std::thread leftThread([this, X, Y, Z, pick_mode, angle]() {
            leftArm->mode_controll( X,  Y,  Z, pick_mode, angle);
        });
        leftThread.join();
        Action_Done_Callback("Done");
    } else if (arm == "right") {
        std::thread rightThread([this, X, Y, Z, pick_mode, angle]() {
            rightArm->mode_controll( X,  Y,  Z, pick_mode, angle);
        });
        rightThread.join();
        Action_Done_Callback("Done");
    } else {
        std::cout << "Error: Unknown arm specified. Use 'left' or 'right'." << std::endl;
    }
    

}

void Robot::posture_singleArmMove(std::string arm, double ox_deg, double oy_deg, double oz_deg, double X, double Y, double Z)
{
    if (arm == "left") {
        std::thread leftThread([this, ox_deg, oy_deg, oz_deg, X, Y, Z]() {
            leftArm->Trajectory_Planning_NoCheck(ox_deg, oy_deg, oz_deg, X, Y , Z);
        });
        leftThread.join();
        Action_Done_Callback("Done");
    } else if (arm == "right") {
        std::thread rightThread([this, ox_deg, oy_deg, oz_deg, X, Y, Z]() {
            rightArm->Trajectory_Planning_NoCheck(ox_deg, oy_deg, oz_deg, X , Y , Z);
        });
        rightThread.join();
        Action_Done_Callback("Done");
    } else {
        std::cout << "Error: Unknown arm specified. Use 'left' or 'right'." << std::endl;
    }

}


void Robot::closeGripper(std::string arm)
{
    if (arm == "left") {
        leftArm->closeGripper();
    } else if (arm == "right") {
        rightArm->closeGripper();
    } else {
        std::cout << "Error: Unknown arm specified. Use 'left' or 'right'." << std::endl;
    }
}
void Robot::openGripper(std::string arm)
{
    if (arm == "left") {
        
        leftArm->openGripper();
    } else if (arm == "right") {

        rightArm->openGripper();
    } else {
        std::cout << "Error: Unknown arm specified. Use 'left' or 'right'." << std::endl;
    }
}
void Robot::GripperController(std::string arm, float angle)
{
    std::this_thread::sleep_for(std::chrono::milliseconds(200));
    if (arm == "left") {
        leftArm->Grippercontrol(angle);
    } else if (arm == "right") {
        rightArm->Grippercontrol(angle);
    } else {
        std::cout << "Error: Unknown arm specified. Use 'left' or 'right'." << std::endl;
    }
}

void Robot::refineGripper_thread(std::string arm, float adjustment, double angle)
{
    // std::thread ArmThread([this, arm, adjustment]() {
    //     refineGripperPosition(arm, adjustment);
    // });
    // ArmThread.join();
    // // 這裡可以加一點延遲，確保手臂穩定
    // std::this_thread::sleep_for(std::chrono::milliseconds(500));
    // // (夾爪角度)
    // std::thread gripperThread([this, arm, angle]() {
    //     GripperController(arm, angle);
    // });
    // gripperThread.join();  
    // std::this_thread::sleep_for(std::chrono::milliseconds(500));
    refineGripperPosition(arm, adjustment);
    std::this_thread::sleep_for(std::chrono::milliseconds(500));
    GripperController(arm, angle);
    std::this_thread::sleep_for(std::chrono::milliseconds(500));
    
}

void Robot::linear_gripper_control(std::string arm)
{

    refineGripper_thread(arm , 10, 55.0);
    refineGripper_thread(arm , 6.8, 100.0); //8//7
    // refineGripper_thread(arm , 3, 125.0); //8
    // refineGripper_thread(arm , 3.8, 250.0); //8
    refineGripper_thread(arm , 6.5, 250.0); //7
    // refineGripper_thread(arm , 10, 100.0);
    // refineGripper_thread(arm , 9, 250.0);

    // closeGripper(arm);
}
void Robot::refineGripperPosition(std::string arm, float adjustment)
{
    if (arm == "left") {
        std::cout<<"current_position_: "<<leftArm->current_position_.transpose()<<std::endl;
        Vector3d retreat_pos = leftArm->computeRetreatAlongZ(adjustment);
        Vector4d world_target=leftArm->transformToWorldPosition(retreat_pos);
        std::cout<<"world target: "<<world_target.transpose()<<std::endl;
        std::cout<<"pick type: "<<leftArm->pick_type<<std::endl;
        
        leftArm->mode_controll( world_target[0],  world_target[1],  world_target[2], leftArm->pick_type, leftArm->angle_shift);
     
    } else if (arm == "right") {
        Vector3d retreat_pos = rightArm->computeRetreatAlongZ(adjustment);
        Vector4d world_target=rightArm->transformToWorldPosition(retreat_pos);
        std::cout<<"world target: "<<world_target.transpose()<<std::endl;
        std::cout<<"pick type: "<<rightArm->pick_type<<std::endl;
        rightArm->mode_controll( world_target[0],  world_target[1],  world_target[2], rightArm->pick_type, rightArm->angle_shift);
        
    } else {
        std::cout << "Error: Unknown arm specified. Use 'left' or 'right'." << std::endl;
    }
}


void Robot::waitForArm(string arm)
{
 std::cout<<"Waiting for "<<arm<<" arm to finish movement..."<<std::endl;
}
void Robot::Neckcontrol(float yaw_deg, float pitch_deg)
{
    neck->SetMotorAngle(0, yaw_deg);
    neck->SetMotorAngle(1, pitch_deg);
}

void Robot::LookTable()
{
    neck->SetMotorAngle(0, 0.0);
    neck->SetMotorAngle(1, 76.0);
    std::this_thread::sleep_for(std::chrono::seconds(2));
}

/* transform matrices
cx,cy,cz: position in endeffector frame (by  camera_to_ee_transform() function in camera_detector.py)

camera_to_base_transform : transform a position from endeffector frame to base frame
camera_to_world_transform : transform a position from endeffector frame to world frame
camera_id : 1->left 2->right



*/

Vector3d  Robot::camera_to_base_transform(double cx, double cy, double cz, int camera_id)
{
    Vector4d base_target;
    if (camera_id == 1){
        base_target = leftArm->EEtransformTobasePosition(Vector3d(cx,cy,cz));


    }else if (camera_id == 2){
        base_target = rightArm->EEtransformTobasePosition(Vector3d(cx,cy,cz));
    }else{
        std::cout<<"Unknown camera id"<<std::endl;
    }
    return Vector3d(base_target[0], base_target[1], base_target[2]);
}
Vector3d Robot::camera_to_world_transform(double cx, double cy, double cz, int camera_id)
{
    Vector4d  world_target;

    Vector3d base_target=camera_to_base_transform(cx, cy, cz, camera_id);
    if (camera_id == 1){
        world_target = leftArm->transformToWorldPosition(base_target);


    }else if (camera_id == 2){
        world_target = rightArm->transformToWorldPosition(base_target);
    }else{
        std::cout<<"Unknown camera id"<<std::endl;
    }
    return Vector3d(world_target[0], world_target[1], world_target[2]);
}

void Robot::commandCallback(const std_msgs::String::ConstPtr& msg)
{
    try {
        json j = json::parse(msg->data);
        
        // 檢查 action 欄位來分辨命令類型
        std::string action = j["action"];
        
        // Robot* robot = Robot::GetRobot();
        
        if (action == "synchronize_move") {
            // 處理同步移動命令
            double x = j["x"];
            double y = j["y"];
            double z = j["z"];
            std::string pick_mode = j["pick_mode"];
            double object_width = j["object_width"];
            
            ROS_INFO("synchronize_move: x=%.2f, y=%.2f, z=%.2f", x, y, z);
            std::this_thread::sleep_for(std::chrono::seconds(1));
            synchronizeMove(x, y, z, pick_mode, object_width);
            Action_Done_Callback("Done");
            
        } else if (action == "single_move") {
            // 處理單一移動命令
            std::string arm = j["arm"];
            double x = j["x"];
            double y = j["y"];
            double z = j["z"];
            std::string pick_mode = j["pick_mode"];
            double angle = j["angle"];
            
            ROS_INFO("single_move: arm=%s, x=%.2f, y=%.2f, z=%.2f", arm.c_str(), x, y, z);
            std::this_thread::sleep_for(std::chrono::seconds(1));
            singleArmMove(arm, x, y, z, pick_mode, angle);
            // robot->singleMove(arm, x, y, z, pick_mode, angle);
            
            // robot->pick(obj_id, x, y, z);
            
        } else if (action == "dual_move") {
            // 處理雙手移動命令
            double LX = j["left"]["x"];
            double LY = j["left"]["y"];
            double LZ = j["left"]["z"];
            std::string Lpick_mode = j["left"]["pick_mode"];
            double Langle = j["left"]["angle"];
            
            double RX = j["right"]["x"];
            double RY = j["right"]["y"];
            double RZ = j["right"]["z"];
            std::string Rpick_mode = j["right"]["pick_mode"];
            double Rangle = j["right"]["angle"];

            ROS_INFO("dual_move: Left(%.2f, %.2f, %.2f) Left pick_mode=%s, angle=%.2f ",
                     LX, LY, LZ, Lpick_mode.c_str(), Langle);
            ROS_INFO("dual_move: Right(%.2f, %.2f, %.2f) Right pick_mode=%s, angle=%.2f",
                     RX, RY, RZ, Rpick_mode.c_str(), Rangle);
            std::this_thread::sleep_for(std::chrono::seconds(1));
            separateMove(LX, LY, LZ, Lpick_mode, Langle,
                         RX, RY, RZ, Rpick_mode, Rangle);
            // robot->separateMove(LX, LY, LZ, Lpick_mode, Langle,
            //                     RX, RY, RZ, Rpick_mode, Rangle);
            
        }else if (action == "close_gripper") {
            std::string arm = j["arm"];
            // float angle = j["angle"];
            ROS_INFO("close_gripper: arm=%s", arm.c_str());
            if (arm == "both") {
                std::thread leftThread([&]() {
                    linear_gripper_control("left");
                    // GripperController("left", angle);
                });
                std::thread rightThread([&]() {
                    linear_gripper_control("right");
                    // GripperController("right", angle);
                });
                leftThread.join();
                rightThread.join();
                Action_Done_Callback("Done");    
            } else {
                std::thread gripperThread([&]() {
                    linear_gripper_control(arm);
                    // GripperController(arm, angle);
                });
                gripperThread.join(); 
                Action_Done_Callback("Done");
                // linear_gripper_control(arm);
                // GripperController(arm, angle);
            }
            
        }else if (action == "close_gripper_ang") {
            std::string arm = j["arm"];
            float angle = j["angle"];
            ROS_INFO("close_gripper_ang: arm=%s", arm.c_str());
            if (arm == "both") {
                std::thread leftThread([&]() {
                    
                    GripperController("left", angle);
                });
                std::thread rightThread([&]() {
                        
                    GripperController("right", angle);
                });
                leftThread.join();
                rightThread.join();
                Action_Done_Callback("Done");    
            } else {
                std::thread gripperThread([&]() {
                    GripperController(arm, angle);
                });
                gripperThread.join(); 
                Action_Done_Callback("Done");
                // linear_gripper_control(arm);
                // GripperController(arm, angle);
            }
            
        } else if (action == "open_gripper") {
            std::string arm = j["arm"];
            ROS_INFO("open_gripper: arm=%s", arm.c_str());
            if (arm == "both") {
                std_msgs::String::Ptr msg(new std_msgs::String());
                msg->data = "我的雙手要放手了喔～";
                VoiceCommandCallback(msg);
                std::thread leftThread([&]() {
                    openGripper("left");
                });
                std::thread rightThread([&]() {
                    openGripper("right");
                });
                leftThread.join();
                rightThread.join();
                Action_Done_Callback("Done");    
            } else {
                if (arm == "left") {
                    std_msgs::String::Ptr msg(new std_msgs::String());
                    msg->data = "我的左手要放手了喔～";
                    VoiceCommandCallback(msg);
                } else if (arm == "right") {
                    std_msgs::String::Ptr msg(new std_msgs::String());
                    msg->data = "我的右手要放手了喔～";
                    VoiceCommandCallback(msg);
                }
                std::thread gripperThread([&]() {
                    openGripper(arm);
                });
                gripperThread.join();
                Action_Done_Callback("Done");
            }
        } else if (action == "neck_control") {
            double yaw_deg = j["yaw"];
            double pitch_deg = j["pitch"];
            ROS_INFO("neck_control: yaw=%.2f, pitch=%.2f", yaw_deg, pitch_deg);
            std::thread neckThread([&]() {
                    Neckcontrol(yaw_deg, pitch_deg);
                    // GripperController("left", angle);
            });
            neckThread.join(); 
            Action_Done_Callback("Done");    

        } else {
            ROS_WARN("unknown: %s", action.c_str());
        }
        
    } catch (const std::exception& e) {
        ROS_ERROR("Error: %s", e.what());
    }
}




void Robot::posture_commandCallback(const std_msgs::String::ConstPtr& msg)
{
    try {
        json j = json::parse(msg->data);
        
        // 檢查 action 欄位來分辨命令類型
        std::string action = j["action"];
        
        // Robot* robot = Robot::GetRobot();
        
        if (action == "pos_synchronize_move") {
            // 處理同步移動命令
            double x = j["x"];
            double y = j["y"];
            double z = j["z"];
            double ox_deg = j["ox_deg"];
            double oy_deg = j["oy_deg"];
            double oz_deg = j["oz_deg"];
           
            double object_width = j["object_width"];
            
            ROS_INFO("pos_synchronize_move: x=%.2f, y=%.2f, z=%.2f, ox=%.2f, oy=%.2f, oz=%.2f", x, y, z, ox_deg, oy_deg, oz_deg);
            std::this_thread::sleep_for(std::chrono::seconds(1));
            posture_synchronizeMove(ox_deg, oy_deg, oz_deg, x, y, z, object_width);
            Action_Done_Callback("Done");
            
        } else if (action == "pos_single_move") {
            // 處理單一移動命令
            std::string arm = j["arm"];
            double x = j["x"];
            double y = j["y"];
            double z = j["z"];
           
            double ox_deg = j["ox_deg"];
            double oy_deg = j["oy_deg"];
            double oz_deg = j["oz_deg"];

            ROS_INFO("pos_single_move: arm=%s, x=%.2f, y=%.2f, z=%.2f, ox=%.2f, oy=%.2f, oz=%.2f", arm.c_str(), x, y, z, ox_deg, oy_deg, oz_deg);
            std::this_thread::sleep_for(std::chrono::seconds(1));
            posture_singleArmMove(arm, ox_deg, oy_deg, oz_deg, x, y, z);
            // robot->singleMove(arm, x, y, z, pick_mode, angle);
            
            // robot->pick(obj_id, x, y, z);
            
        } else if (action == "pos_dual_move") {
            // 處理雙手移動命令
            double LX = j["left"]["x"];
            double LY = j["left"]["y"];
            double LZ = j["left"]["z"];
            double Lox_deg = j["left"]["ox_deg"];
            double Loy_deg = j["left"]["oy_deg"];
            double Loz_deg = j["left"]["oz_deg"];
            
            double RX = j["right"]["x"];
            double RY = j["right"]["y"];
            double RZ = j["right"]["z"];
            double Rox_deg = j["right"]["ox_deg"];
            double Roy_deg = j["right"]["oy_deg"];
            double Roz_deg = j["right"]["oz_deg"];

            ROS_INFO("pos_dual_move: Left(%.2f, %.2f, %.2f) Left(ox=%.2f, oy=%.2f, oz=%.2f)",
                     LX, LY, LZ, Lox_deg, Loy_deg, Loz_deg);
            ROS_INFO("pos_dual_move: Right(%.2f, %.2f, %.2f) Right(ox=%.2f, oy=%.2f, oz=%.2f)",
                     RX, RY, RZ, Rox_deg, Roy_deg, Roz_deg);
            std::this_thread::sleep_for(std::chrono::seconds(1));
            posture_separateMove(Lox_deg, Loy_deg, Loz_deg, LX, LY, LZ,
                                 Rox_deg, Roy_deg, Roz_deg, RX, RY, RZ);
            // robot->separateMove(LX, LY, LZ, Lpick_mode, Langle,
            //                     RX, RY, RZ, Rpick_mode, Rangle);
            
        }else if (action == "gripper_control") {
            std::string arm = j["arm"];
            float angle = j["angle"];
            ROS_INFO("gripper_control: arm=%s", arm.c_str());
            if (arm == "both") {
                std::thread leftThread([&]() {
                    GripperController("left", angle);
                });
                std::thread rightThread([&]() {
                    
                    GripperController("right", angle);
                });
                leftThread.join();
                rightThread.join();
                Action_Done_Callback("Done");    
            } else {
                std::thread gripperThread([&]() {
                   
                    GripperController(arm, angle);
                });
                gripperThread.join(); 
                Action_Done_Callback("Done");
            }
            
            
        } else if (action == "open_gripper") {
            std::string arm = j["arm"];
            ROS_INFO("open_gripper: arm=%s", arm.c_str());
            if (arm == "both") {
                
                std::thread leftThread([&]() {
                    openGripper("left");
                });
                std::thread rightThread([&]() {
                    openGripper("right");
                });
                leftThread.join();
                rightThread.join();
                Action_Done_Callback("Done");    
            } else {
                std::thread gripperThread([&]() {
                    openGripper(arm);
                });
                gripperThread.join();
                Action_Done_Callback("Done");
            }
        } else if (action == "neck_control") {
            double yaw_deg = j["yaw"];
            double pitch_deg = j["pitch"];
            ROS_INFO("neck_control: yaw=%.2f, pitch=%.2f", yaw_deg, pitch_deg);
            std::thread neckThread([&]() {
                    Neckcontrol(yaw_deg, pitch_deg);
                    // GripperController("left", angle);
            });
            neckThread.join(); 
            Action_Done_Callback("Done");    

        } else {
            ROS_WARN("unknown: %s", action.c_str());
        }
        
    } catch (const std::exception& e) {
        ROS_ERROR("Error: %s", e.what());
    }
}

// === 新增：初始化 Publisher ===
void Robot::initPublisher(ros::NodeHandle& nh)
{
    base_point_pub_ = nh.advertise<geometry_msgs::Point>("/base/object_point", 10);
    voice_command_pub_ = nh.advertise<std_msgs::String>("voice_command", 10);
    action_state_pub = nh.advertise<std_msgs::String>("action_state", 10);
    ROS_INFO("Base point publisher initialized on /base/object_point");
    ROS_INFO("Voice command publisher initialized on voice_command");
    transform_server_ = nh.advertiseService("batch_transform", &Robot::batchTransformCallback, this);
    transform_server_L = nh.advertiseService("Arm_batch_transform", &Robot::ArmCameraTransform, this);
    
    ROS_INFO("Batch Transform Service Started!");

}


bool Robot::ArmCameraTransform(robot_core::ArmBatchTransform::Request &req,
                                   robot_core::ArmBatchTransform::Response &res) 
{
    // 檢查資料完整性
    if (req.ids.size() != req.points.size()) {
        ROS_ERROR("Received mismatching IDs and Points size!");
        res.success = false;
        return true;
    }

    ROS_INFO("Received batch request with %lu points", req.points.size());

    // 遍歷所有請求的點
    for (size_t i = 0; i < req.ids.size(); ++i) {
        try {
            // 1. 取出相機座標 (從 Request 列表)
            double cx = req.points[i].x;
            double cy = req.points[i].y;
            double cz = req.points[i].z;

            // 2. [核心邏輯] 進行運算
            if (req.arm != 1 && req.arm != 2) {
                throw std::runtime_error("Invalid arm ID. Must be 1 (left) or 2 (right).");
            }
            else if (req.arm == 1) {
                Left_target_POS = camera_to_world_transform(cx, cy, cz, 1);

                ROS_INFO("Transforming point for LEFT arm: (%.1f, %.1f, %.1f)", cx, cy, cz);
                ROS_INFO("Resulting world position: (%.1f, %.1f, %.1f)", Left_target_POS.x(), Left_target_POS.y(), Left_target_POS.z());
            } else {
                Right_target_POS = camera_to_world_transform(cx, cy, cz, 2);
                ROS_INFO("Transforming point for RIGHT arm: (%.1f, %.1f, %.1f)", cx, cy, cz);
                ROS_INFO("Resulting world position: (%.1f, %.1f, %.1f)", Right_target_POS.x(), Right_target_POS.y(), Right_target_POS.z());
            }
            Eigen::Vector3d target_POS = (req.arm == 1) ? Left_target_POS : Right_target_POS;
            // 3. 填入回傳結果 (Response)
            // 重要：我們把收到的 ID 原封不動傳回去，Python 端才能對應
            res.ids.push_back(req.ids[i]);

            geometry_msgs::Point p_out;
            p_out.x = target_POS.x();
            p_out.y = target_POS.y();
            p_out.z = target_POS.z();
            res.points.push_back(p_out);
          

        } catch (const std::exception& e) {
            ROS_ERROR("Transform failed for ID %d: %s", req.ids[i], e.what());
            // 即使單點失敗，我們也可以選擇繼續做下一個，或者在這裡 return false
            // 建議：失敗的話，可以塞一個特定的錯誤值 (如 NaN) 或者不塞入該 ID
        }
    }

    res.success = true;
    return true; // 回傳 true 代表 Service 通訊本身是成功的
}
bool Robot::batchTransformCallback(robot_core::BatchTransform::Request &req,
                                   robot_core::BatchTransform::Response &res) 
{
    // 檢查資料完整性
    if (req.ids.size() != req.points.size()) {
        ROS_ERROR("Received mismatching IDs and Points size!");
        res.success = false;
        return true;
    }

    ROS_INFO("Received batch request with %lu points", req.points.size());

    // 遍歷所有請求的點
    for (size_t i = 0; i < req.ids.size(); ++i) {
        try {
            // 1. 取出相機座標 (從 Request 列表)
            double cx = req.points[i].x;
            double cy = req.points[i].y;
            double cz = req.points[i].z;

            // 2. [核心邏輯] 呼叫你原本的 neck 物件進行運算
            // 這裡完全保留你原本的寫法
            Eigen::Vector3f base_pos = neck->GetBasePosition(cx, cy, cz);

            // 3. 填入回傳結果 (Response)
            // 重要：我們把收到的 ID 原封不動傳回去，Python 端才能對應
            res.ids.push_back(req.ids[i]);

            geometry_msgs::Point p_out;
            p_out.x = base_pos.x();
            p_out.y = base_pos.y();
            p_out.z = base_pos.z();
            res.points.push_back(p_out);
            // base_point_pub_.publish(p_out);
            // (選用) Log 可以印少一點，不然多個物體會洗版
            // ROS_INFO("Transformed ID %d: (%.1f, %.1f, %.1f)", req.ids[i], p_out.x, p_out.y, p_out.z);

        } catch (const std::exception& e) {
            ROS_ERROR("Transform failed for ID %d: %s", req.ids[i], e.what());
            // 即使單點失敗，我們也可以選擇繼續做下一個，或者在這裡 return false
            // 建議：失敗的話，可以塞一個特定的錯誤值 (如 NaN) 或者不塞入該 ID
        }
    }

    res.success = true;
    return true; // 回傳 true 代表 Service 通訊本身是成功的
}

void Robot::pointCallback(const geometry_msgs::Point::ConstPtr& msg) 
{
    try {
        // 接收相機座標並轉換
        Eigen::Vector3f base_pos = neck->GetBasePosition(msg->x, msg->y, msg->z);
        
        ROS_INFO("Transformed: Camera(%.1f, %.1f, %.1f) -> Base(%.1f, %.1f, %.1f)",
                 msg->x, msg->y, msg->z,
                 base_pos.x(), base_pos.y(), base_pos.z());
        
        // === 發布轉換後的基座標 ===
        geometry_msgs::Point base_msg;
        base_msg.x = base_pos.x();
        base_msg.y = base_pos.y();
        base_msg.z = base_pos.z();
        
        // base_point_pub_.publish(base_msg);
        ROS_INFO("Published base position to /base/object_point");
        
    } catch (const std::exception& e) {
        ROS_ERROR("Transform failed: %s", e.what());
    }
}
void Robot::VoiceCommandCallback(const std_msgs::String::ConstPtr& msg) 
{
    try {
        std_msgs::String voice_msg;
        voice_msg.data = msg->data;
        voice_command_pub_.publish(voice_msg);
        std::this_thread::sleep_for(std::chrono::milliseconds(2000));
        // ROS_INFO("Published voice command: %s", msg->data.c_str());
        
    } catch (const std::exception& e) {
        ROS_ERROR("Voice command publish failed: %s", e.what());
    }
}
void Robot::Action_Done_Callback(string msg_s) 
{
    try {
        
        std_msgs::String action_msg;
        action_msg.data = msg_s;
        action_state_pub.publish(action_msg);
        // ROS_INFO("Published action state: %s", msg->data.c_str());
        
    } catch (const std::exception& e) {
        ROS_ERROR("Action state publish failed: %s", e.what());
    }
}