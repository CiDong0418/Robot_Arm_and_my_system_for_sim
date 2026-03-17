import pyrealsense2 as rs
import numpy as np
import cv2

print("正在尋找並啟動 RealSense D456 相機...")

try:
    # 1. 初始化相機管線 (Pipeline)
    pipeline = rs.pipeline()
    config = rs.config()

    # 2. 設定解析度與影格率 (D456 支援標準的 640x480 @ 30fps)
    config.enable_stream(rs.stream.depth, 640, 480, rs.format.z16, 30)
    config.enable_stream(rs.stream.color, 640, 480, rs.format.bgr8, 30)

    # 3. 正式啟動相機
    pipeline.start(config)
    print("✅ 相機啟動成功！將彈出即時畫面，按 'q' 鍵可關閉視窗。")

    while True:
        # 4. 獲取相機的即時影格（包含彩色與深度）
        frames = pipeline.wait_for_frames()
        depth_frame = frames.get_depth_frame()
        color_frame = frames.get_color_frame()

        if not depth_frame or not color_frame:
            continue

        # 5. 將相機資料轉換為 Numpy 陣列，方便 OpenCV 處理
        depth_image = np.asanyarray(depth_frame.get_data())
        color_image = np.asanyarray(color_frame.get_data())

        # 6. 把深度圖「上色」，讓距離遠近變成明顯的熱像圖漸層
        depth_colormap = cv2.applyColorMap(cv2.convertScaleAbs(depth_image, alpha=0.03), cv2.COLORMAP_JET)

        # 7. 把彩色畫面跟深度畫面「左右拼接」在一起
        images = np.hstack((color_image, depth_colormap))

        # 8. 顯示視窗
        cv2.imshow('RealSense D456 - Eye in Hand Test', images)

        # 9. 偵測鍵盤，按下 'q' 或是 ESC 就退出
        key = cv2.waitKey(1)
        if key & 0xFF == ord('q') or key == 27:
            break

except Exception as e:
    print(f"❌ 發生錯誤: {e}")
    print("💡 提示：確認相機 USB 是否有插好？是否被其他程式佔用？")

finally:
    # 10. 安全關閉相機管線與視窗
    try:
        pipeline.stop()
        cv2.destroyAllWindows()
        print("相機已安全關閉。")
    except:
        pass