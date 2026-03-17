#include "GripperController.h"
#include <iostream>
#include <memory>

int main() {
    std::string port = "/dev/ttyUSB0";  // 根據你實際的 U2D2 port 選擇 ttyUSB0 或 ttyUSB1
    uint8_t id = 31;                     // 夾爪 ID（預設是 1）
    int baudrate = 4000000;            // 預設是 2 Mbps

    std::shared_ptr<GripperController> gripper = std::make_shared<GripperController>(port, id, baudrate);

    std::string input;
    while (true) {
        std::cout << "Enter 'o' to open, 'c' to close, or 'q' to quit: ";
        std::cin >> input;

        if (input == "o") {
            // gripper->openGripper(MotorUnion::tmp_portHandler);
            // SetMotor_Angle(7, 5);
            // WaitMotorArrival(7);
        } else if (input == "c") {
            // gripper->closeGripper(MotorUnion::tmp_portHandler);
        } else if (input == "q") {
            break;
        } else {
            std::cout << "Invalid input." << std::endl;
        }
    }

    return 0;
}