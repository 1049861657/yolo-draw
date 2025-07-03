"""
快捷键管理组件 - 统一管理应用程序的所有快捷键
"""
from enum import Enum
from typing import Dict, Optional

from PySide6.QtCore import QObject, Signal, Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QWidget


class ShortcutAction(Enum):
    """快捷键动作枚举"""
    ADD_BBOX = "add_bbox"                    # Q键：添加标注框
    NAVIGATE_UP = "navigate_up"              # W键：向上导航
    NAVIGATE_DOWN = "navigate_down"          # S键：向下导航
    CLEAR_LABELS = "clear_labels"            # T键：清空标签
    BATCH_DISCARD = "batch_discard"          # U键：批量丢弃
    SELECT_BBOX = "select_bbox"              # 1-9键：选择标注框
    YOLO_PREDICT = "yolo_predict"            # *键：YOLO预测
    ACCEPT_PREDICTIONS = "accept_predictions" # +键：接受预测
    REJECT_PREDICTIONS = "reject_predictions" # -键：拒绝预测


class KeyboardShortcutManager(QObject):
    """键盘快捷键管理器"""
    
    # 信号定义
    shortcut_triggered = Signal(str, object)  # 快捷键触发信号 (action, data)
    
    def __init__(self, parent_widget: QWidget):
        """初始化快捷键管理器
        
        Args:
            parent_widget: 父窗口部件
        """
        super().__init__()
        self.parent_widget = parent_widget
        self.shortcuts: Dict[str, QShortcut] = {}
        self._setup_shortcuts()
    
    def _setup_shortcuts(self):
        """设置所有快捷键"""
        # 定义快捷键配置 (键, 动作, 描述)
        shortcut_configs = [
            (Qt.Key.Key_Q, ShortcutAction.ADD_BBOX, "添加标注框"),
            (Qt.Key.Key_W, ShortcutAction.NAVIGATE_UP, "向上导航"),
            (Qt.Key.Key_S, ShortcutAction.NAVIGATE_DOWN, "向下导航"),
            (Qt.Key.Key_T, ShortcutAction.CLEAR_LABELS, "清空标签"),
            (Qt.Key.Key_U, ShortcutAction.BATCH_DISCARD, "批量丢弃"),
            (Qt.Key.Key_Asterisk, ShortcutAction.YOLO_PREDICT, "YOLO预测"),
            (Qt.Key.Key_Plus, ShortcutAction.ACCEPT_PREDICTIONS, "接受预测"),
            (Qt.Key.Key_Minus, ShortcutAction.REJECT_PREDICTIONS, "拒绝预测"),
        ]
        
        # 创建基本快捷键
        for key, action, description in shortcut_configs:
            self._create_shortcut(key, action.value, description)
        
        # 创建数字键快捷键 (1-9)
        for i in range(1, 10):
            key = getattr(Qt.Key, f"Key_{i}")
            self._create_shortcut(key, ShortcutAction.SELECT_BBOX.value, f"选择标注框{i}", i-1)
    
    def _create_shortcut(self, key: Qt.Key, action: str, description: str, data: Optional[int] = None):
        """创建单个快捷键
        
        Args:
            key: 按键
            action: 动作名称
            description: 描述
            data: 额外数据
        """
        shortcut = QShortcut(QKeySequence(key), self.parent_widget)
        shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
        
        # 使用lambda捕获data参数
        if data is not None:
            shortcut.activated.connect(lambda a=action, d=data: self.shortcut_triggered.emit(a, d))
        else:
            shortcut.activated.connect(lambda a=action: self.shortcut_triggered.emit(a, None))
        
        # 存储快捷键引用
        shortcut_id = f"{action}_{data}" if data is not None else action
        self.shortcuts[shortcut_id] = shortcut
    
    def enable_shortcut(self, action: str, data: Optional[int] = None):
        """启用指定快捷键
        
        Args:
            action: 动作名称
            data: 额外数据
        """
        shortcut_id = f"{action}_{data}" if data is not None else action
        if shortcut_id in self.shortcuts:
            self.shortcuts[shortcut_id].setEnabled(True)
    
    def disable_shortcut(self, action: str, data: Optional[int] = None):
        """禁用指定快捷键
        
        Args:
            action: 动作名称
            data: 额外数据
        """
        shortcut_id = f"{action}_{data}" if data is not None else action
        if shortcut_id in self.shortcuts:
            self.shortcuts[shortcut_id].setEnabled(False)
    
    def enable_all_shortcuts(self):
        """启用所有快捷键"""
        for shortcut in self.shortcuts.values():
            shortcut.setEnabled(True)
    
    def disable_all_shortcuts(self):
        """禁用所有快捷键"""
        for shortcut in self.shortcuts.values():
            shortcut.setEnabled(False)
    
    def get_shortcut_info(self) -> Dict[str, str]:
        """获取快捷键信息
        
        Returns:
            快捷键信息字典
        """
        return {
            "Q": "添加标注框",
            "W": "向上导航",
            "S": "向下导航", 
            "T": "清空标签",
            "U": "批量丢弃",
            "1-9": "选择标注框",
            "*": "YOLO预测",
            "+": "接受预测",
            "-": "拒绝预测"
        } 