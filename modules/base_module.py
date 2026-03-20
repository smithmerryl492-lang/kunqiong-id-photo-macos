"""功能模块基类"""
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from PyQt6.QtWidgets import QWidget
import os
from i18n import tr


class BaseModule(ABC):
    """功能模块基类，所有功能模块都应继承此类"""

    def __init__(self, name: str, description: str, icon: str):
        self.name = name
        self.description = description
        self.icon = icon
        self.model = None
        self.model_loaded = False

    @abstractmethod
    def load_model(self):
        """加载模型（延迟加载，首次使用时调用）"""
        pass

    @abstractmethod
    def process(self, image_path: str, **kwargs) -> str:
        """处理图片"""
        pass

    def get_ui_widget(self) -> Optional[QWidget]:
        return None

    def validate_input(self, image_path: str) -> tuple[bool, str]:
        if not image_path:
            return False, "请选择图片"
        if not os.path.exists(image_path):
            return False, "图片文件不存在"
        valid_extensions = ['.jpg', '.jpeg', '.png', '.bmp', '.webp']
        ext = os.path.splitext(image_path)[1].lower()
        if ext not in valid_extensions:
            return False, f"不支持的图片格式: {ext}"
        return True, ""

    def ensure_model_loaded(self):
        if not self.model_loaded:
            self.load_model()
            self.model_loaded = True

    def get_name(self) -> str:
        return self.name

    def get_description(self) -> str:
        if hasattr(self, "description_key"):
            return tr(self.description_key)
        return self.description

    def get_icon(self) -> str:
        return self.icon

    def get_system_requirements(self) -> dict:
        return {
            'min_cpu': tr('preview.cpu_cores', count=4),
            'min_ram': tr('preview.memory_gb', count=8),
            'rec_cpu': tr('preview.cpu_cores', count=8),
            'rec_ram': tr('preview.memory_gb', count=16),
        }
