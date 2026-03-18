from abc import ABC, abstractmethod

from .action_runtime import get_action_runtime

class BaseAction(ABC):
    """
    所有機器人動作的基礎父類別 (Abstract Base Class)
    """
    def __init__(self, task_data: dict):
        self.task_data = task_data
        self.action_type = task_data.get("action_type", "UNKNOWN")
        self.global_id = task_data.get("global_id", "N/A")
        self.robot_control, self.camera_transfer = get_action_runtime()

    @abstractmethod
    def execute(self) -> bool:
        """
        每個子類別都必須實作這個方法。
        回傳 True 代表動作成功執行，False 代表失敗。
        """
        pass