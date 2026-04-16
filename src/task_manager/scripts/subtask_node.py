#!/usr/bin/env python3
import rospy
import sys
import os
import json
from std_msgs.msg import String
from std_srvs.srv import Trigger
from datetime import datetime

# 訂閱話題: /high_level_stream (String, JSON 格式)
# 發布話題: /subtasks_queue (String, JSON 格式)

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))
from task_module.subtask_parser import decompose_task
from task_module.domain_catalog import OBJECT_CATALOG, OPERABLE_LOCATIONS

# 儲存原子任務 log 的路徑
LOG_PATH = os.path.join(os.path.dirname(__file__), '../subtask_log.json')

class SubtaskNode:
    def __init__(self):
        rospy.init_node('subtask_node', anonymous=True)

        # 訂閱：大任務輸出 (來自 high_level_node)
        self.sub = rospy.Subscriber('/high_level_stream', String, self.subtask_callback)
        self.scan_replan_sub = rospy.Subscriber('/scan_runtime_result', String, self.scan_replan_callback)

        # 發布：拆解完的小任務序列 (準備給 Scheduler 排程器)
        self.pub = rospy.Publisher('/subtasks_queue', String, queue_size=10)

        # 執行期插單任務 ID，避免與 high_level_node 指派的短 ID 相撞
        self.runtime_task_id_counter = 10000
        self.valid_object_names = {obj["object_name"] for obj in OBJECT_CATALOG}
        self.location_name_by_id = {loc["location_id"]: loc["location_name"] for loc in OPERABLE_LOCATIONS}

        # 每次節點啟動時清空 log，準備這次新的紀錄
        self._log_all = []
        self._init_log()

        rospy.loginfo("=== [Node 3] Sub-Task Decomposer Ready ===")
        rospy.loginfo(f"📝 原子任務 log 將儲存至: {LOG_PATH}")

    def _init_log(self):
        """每次節點啟動時清空 log 檔"""
        with open(LOG_PATH, 'w', encoding='utf-8') as f:
            json.dump([], f, ensure_ascii=False, indent=2)

    def _save_to_log(self, task_id, task_name, subtasks):
        """把這批原子任務追加寫入 log 檔"""
        self._log_all.append({
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "parent_task_id": task_id,
            "parent_task_name": task_name,
            "subtasks": subtasks
        })
        with open(LOG_PATH, 'w', encoding='utf-8') as f:
            json.dump(self._log_all, f, ensure_ascii=False, indent=2)

    @staticmethod
    def _contains_runtime_scan_marker(task_name, description):
        text = f"{task_name} {description}".lower()
        keywords = [
            "逐項插入",
            "插入後續",
            "掃描後",
            "看完後",
            "根據看到",
            "先掃描",
        ]
        return any(word in text for word in keywords)

    @staticmethod
    def _summarize_scan_objects(scan_objects):
        if not isinstance(scan_objects, list) or not scan_objects:
            return "未辨識到可用物件"

        chunks = []
        for item in scan_objects:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name", "")).strip()
            if not name:
                continue
            count = item.get("count", 1)
            try:
                count = int(count)
            except Exception:
                count = 1
            if count > 1:
                chunks.append(f"{name} x{count}")
            else:
                chunks.append(name)
        return ", ".join(chunks) if chunks else "未辨識到可用物件"

    @staticmethod
    def _normalize_scan_name(name):
        key = str(name or "").strip().lower()
        name_map = {
            "water": "mineral_water",
            "bottled_water": "mineral_water",
            "mineral water": "mineral_water",
            "medicine jar": "medicine_jar",
            "medicine_jar": "medicine_jar",
            "book": "notebook",
            "drawer": "drawer",
            "remote_control": "remote_control",
            "a_carton_of_milk": "milk",
            "green_cup": "green_cup",
        }
        return name_map.get(key, key)

    def _build_involved_items_from_scan(self, scan_objects, location_id):
        items = []
        try:
            canonical_location = int(location_id)
        except Exception:
            canonical_location = 1

        location_name = self.location_name_by_id.get(canonical_location, "dining_table")

        for item in (scan_objects or []):
            if not isinstance(item, dict):
                continue
            raw_name = item.get("name")
            if raw_name is None:
                continue
            obj_name = SubtaskNode._normalize_scan_name(raw_name)
            if obj_name not in self.valid_object_names:
                continue
            items.append({
                "item_name": obj_name,
                "location": location_name,
                "location_id": canonical_location,
            })
        return items

    def _publish_subtasks(self, task_id, task_name, subtasks):
        self._save_to_log(task_id, task_name, subtasks)
        result_json = json.dumps(subtasks, ensure_ascii=False)
        self.pub.publish(result_json)
        rospy.loginfo(f"📤 任務 [{task_id}] 拆解完成！已發送 {len(subtasks)} 個原子動作。")
        rospy.loginfo(f"💾 已儲存至 {LOG_PATH}")

    def _trigger_reschedule(self):
        try:
            rospy.wait_for_service('/start_scheduling', timeout=2.0)
            call = rospy.ServiceProxy('/start_scheduling', Trigger)
            response = call()
            rospy.loginfo(f"[SubtaskNode] 已觸發重排: success={response.success}, msg={response.message}")
        except Exception as error:
            rospy.logwarn(f"[SubtaskNode] 觸發 /start_scheduling 失敗: {error}")

    def _prepare_scan_runtime_tasks(self, high_level_task, subtasks):
        task_name = high_level_task.get('name', 'Unknown')
        description = high_level_task.get('description', '')

        has_scan = any(s.get('action_type') == 'SCAN_TABLE_OBJECTS' for s in subtasks)
        runtime_mode = has_scan and self._contains_runtime_scan_marker(task_name, description)
        if not runtime_mode:
            return subtasks

        scan_subtasks = [s for s in subtasks if s.get('action_type') == 'SCAN_TABLE_OBJECTS']
        if not scan_subtasks:
            return subtasks

        for sub in scan_subtasks:
            sub['scan_capture_required'] = True
            sub['runtime_replan_enabled'] = True
            sub['post_scan_instruction'] = description or task_name
            sub['dependencies'] = []

        rospy.loginfo(
            f"[SubtaskNode] 任務 [{high_level_task.get('id', -1)}] 啟用掃描後插單模式，"
            f"保留 {len(scan_subtasks)} 個 SCAN 任務。"
        )
        return scan_subtasks

    def subtask_callback(self, msg):

        try:
            high_level_task = json.loads(msg.data)

            task_id = int(high_level_task.get('id', -1))  # 強制轉成整數
            task_name = high_level_task.get('name', 'Unknown')

            rospy.loginfo(f"📥 收到大任務 [{task_id}] {task_name}，開始細部拆解...")

            # call subtask_parser.py
            subtasks = decompose_task(high_level_task)
            subtasks = self._prepare_scan_runtime_tasks(high_level_task, subtasks)

            if subtasks:
                self._publish_subtasks(task_id, task_name, subtasks)
            else:
                rospy.logwarn(f"⚠️ 任務 [{task_id}] 拆解失敗或回傳空值。")

        except json.JSONDecodeError:
            rospy.logerr("收到無效的 JSON 格式，無法解析。")
        except Exception as e:
            rospy.logerr(f"處理過程發生錯誤: {e}")

    def scan_replan_callback(self, msg):
        try:
            payload = json.loads(msg.data)
            if not isinstance(payload, dict):
                rospy.logwarn("[SubtaskNode] scan_replan payload 非 dict，忽略")
                return

            if not payload.get("runtime_replan_enabled", False):
                return

            instruction = str(payload.get("post_scan_instruction", "")).strip()
            if not instruction:
                rospy.logwarn("[SubtaskNode] 缺少 post_scan_instruction，略過執行期插單")
                return

            scan_objects = payload.get("objects", [])
            location_id = int(payload.get("location_id", 1))
            object_summary = self._summarize_scan_objects(scan_objects)
            image_path = str(payload.get("image_path", "")).strip()

            runtime_task_id = self.runtime_task_id_counter
            self.runtime_task_id_counter += 1

            runtime_description = (
                f"掃描完成，位置 location_id={location_id}。"
                f"目前看到：{object_summary}。"
                f"後續指示：{instruction}。"
            )
            if image_path:
                runtime_description += f" 影像紀錄：{image_path}。"

            runtime_task = {
                "id": runtime_task_id,
                "name": f"Runtime scan follow-up from {payload.get('scan_task_global_id', 'unknown')}",
                "description": runtime_description,
                "involved_items": self._build_involved_items_from_scan(scan_objects, location_id),
                "time_constraints": {},
                "urgency_level": payload.get("urgency_level", "normal"),
                "urgency_score": int(payload.get("urgency_score", 0) or 0),
            }

            rospy.loginfo(
                f"[SubtaskNode] 收到掃描插單請求，生成執行期任務 id={runtime_task_id}, "
                f"objects={object_summary}"
            )

            subtasks = decompose_task(runtime_task)
            if not subtasks:
                rospy.logwarn(f"[SubtaskNode] 執行期插單任務 {runtime_task_id} 拆解失敗")
                return

            self._publish_subtasks(runtime_task_id, runtime_task["name"], subtasks)
            self._trigger_reschedule()

        except Exception as error:
            rospy.logerr(f"[SubtaskNode] scan_replan_callback 失敗: {error}")

if __name__ == '__main__':
    node = SubtaskNode()
    rospy.spin()
