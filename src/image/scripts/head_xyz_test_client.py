#!/usr/bin/env python3
"""
head_xyz_test_client.py
=======================
互動式測試節點：等待鍵盤輸入目標物品名稱，發送偵測請求並顯示結果，
完成後繼續等待下一次輸入，不自動關閉。

用法:
    rosrun image head_xyz_test_client.py
    > 輸入要辨識的物品（q 退出）: cup
    > 輸入要辨識的物品（q 退出）: bottle
    > 輸入要辨識的物品（q 退出）: q
"""
import threading
import rospy
from std_msgs.msg import String, Float32
from geometry_msgs.msg import PointStamped


class HeadXYZTestClient:

    def __init__(self):
        rospy.init_node("head_xyz_test_client", anonymous=True)

        # 用 Event 等待本次辨識的結果到齊
        self._result_event = threading.Event()

        # ── 訂閱結果 topics ──
        rospy.Subscriber("/head_detection/xyz",    PointStamped, self._cb_xyz)
        rospy.Subscriber("/head_detection/radius", Float32,      self._cb_radius)
        rospy.Subscriber("/head_detection/status", String,       self._cb_status)

        # ── 發布目標 ──
        self._pub = rospy.Publisher(
            "/head_detection/target", String, queue_size=1)

        # 等 publisher 連線完成
        rospy.sleep(0.8)

        self._run_loop()

    # ── 主迴圈 ────────────────────────────────────────────────────────────

    def _run_loop(self):
        """等鍵盤輸入 → 發送 → 等結果 → 再等輸入（無限迴圈）。"""
        print("\n" + "="*52)
        print("  head_xyz_test_client  |  輸入 q 退出")
        print("="*52)

        while not rospy.is_shutdown():
            try:
                target = input("\n> 輸入要辨識的物品（q 退出）: ").strip()
            except (EOFError, KeyboardInterrupt):
                break

            if target.lower() in ("q", "quit", "exit", ""):
                rospy.loginfo("[test_client] 使用者退出。")
                break

            # 重置 event，發送目標
            self._result_event.clear()
            msg = String()
            msg.data = target
            self._pub.publish(msg)
            rospy.loginfo(f"[test_client] 已發送目標：'{target}'，等待結果…")

            # 等待結果（最多 30 秒）
            if not self._result_event.wait(timeout=30.0):
                print("  ⚠️  等待逾時（30秒），請確認偵測節點是否正常運作。")

    # ── Callbacks ─────────────────────────────────────────────────────────

    def _cb_xyz(self, msg: PointStamped) -> None:
        print(f"\n{'='*52}")
        print(f"  [XYZ] 表面中心座標（相機座標系）")
        print(f"  X = {msg.point.x: .3f} mm")
        print(f"  Y = {msg.point.y: .3f} mm")
        print(f"  Z = {msg.point.z: .3f} mm")
        print(f"{'='*52}")

    def _cb_radius(self, msg: Float32) -> None:
        print(f"  [R]   半徑 = {msg.data:.3f} mm")

    def _cb_status(self, msg: String) -> None:
        status = msg.data
        if status.startswith("OK"):
            print(f"  [狀態] ✅ {status}")
        else:
            print(f"  [狀態] ❌ {status}")
        # 收到 status（不論成功/失敗）代表本次辨識結束，解除等待
        self._result_event.set()


if __name__ == "__main__":
    HeadXYZTestClient()
