#!/usr/bin/env python3
import rospy
from std_msgs.msg import String
from colorama import Fore, Style, init

# 初始化顏色
init()

# 功能說明:
# 這一個程式負責讀取使用者輸入，並將輸入的文字發布到 ROS 話題 /user_command 上

def main():
    rospy.init_node('user_input_node', anonymous=True)
    
    
    pub = rospy.Publisher('/user_command', String, queue_size=50)
    
    print(f"{Fore.GREEN}=== ROS Task Input Node Started ==={Style.RESET_ALL}")
    print(f"{Fore.YELLOW}[Input] Please type your command (e.g., 'After 2pm, clean the room'):{Style.RESET_ALL}")

    while not rospy.is_shutdown():
        try:
            
            user_text = input(f"{Fore.CYAN}User > {Style.RESET_ALL}") # 藍色
            
            if not user_text.strip():
                continue
            
            if user_text.lower() in ['exit', 'q']:
                break
            
            # 發布訊息
            rospy.loginfo(f"Sending Command: {user_text}")
            pub.publish(user_text)
            
        except (EOFError, KeyboardInterrupt):
            break

if __name__ == '__main__':
    try:
        main()
    except rospy.ROSInterruptException:
        pass