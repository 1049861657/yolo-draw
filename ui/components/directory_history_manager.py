"""
目录历史记录管理组件
负责管理源目录和目标目录的历史记录功能
"""
import os
from PySide6.QtCore import QObject, QSettings
from PySide6.QtWidgets import QComboBox, QMessageBox


class DirectoryHistoryManager(QObject):
    """目录历史记录管理器"""
    
    def __init__(self, parent=None):
        """初始化目录历史记录管理器"""
        super().__init__(parent)
        
        # 使用QSettings来持久化存储历史记录
        self.settings = QSettings("YoloAnnotationTool", "DirectoryHistory")
        
        # 最大历史记录数量
        self.max_history_count = 5
    
    def load_directory_history(self, key):
        """加载目录历史记录
        
        Args:
            key: 历史记录的键名
            
        Returns:
            list: 历史记录列表
        """
        history = self.settings.value(key, [])
        if isinstance(history, str):
            # 兼容旧版本，如果是字符串则转换为列表
            history = [history] if history else []
        elif not isinstance(history, list):
            history = []
        return history
    
    def save_directory_history(self, key, history):
        """保存目录历史记录
        
        Args:
            key: 历史记录的键名
            history: 历史记录列表
        """
        # 确保历史记录不超过最大数量
        if len(history) > self.max_history_count:
            history = history[:self.max_history_count]
        
        self.settings.setValue(key, history)
        self.settings.sync()  # 立即同步到磁盘
    
    def add_to_history(self, combo_box, directory, key):
        """添加目录到历史记录
        
        Args:
            combo_box: 目标下拉框组件
            directory: 要添加的目录路径
            key: 历史记录的键名
        """
        if not directory or not os.path.exists(directory):
            return
        
        # 获取当前历史记录
        current_items = [combo_box.itemText(i) for i in range(combo_box.count())]
        
        # 如果目录已存在，先移除
        if directory in current_items:
            current_items.remove(directory)
        
        # 添加到列表开头
        current_items.insert(0, directory)
        
        # 限制历史记录数量
        if len(current_items) > self.max_history_count:
            current_items = current_items[:self.max_history_count]
        
        # 更新下拉框
        combo_box.clear()
        combo_box.addItems(current_items)
        combo_box.setCurrentText(directory)
        
        # 保存到设置
        self.save_directory_history(key, current_items)
    
    def clear_history(self, combo_box, key, history_type_name, parent=None):
        """清除历史记录
        
        Args:
            combo_box: 目标下拉框组件
            key: 历史记录的键名
            history_type_name: 历史记录类型名称（用于显示）
            parent: 父窗口（用于消息框）
            
        Returns:
            bool: 是否成功清除
        """
        reply = QMessageBox.question(
            parent, "确认清除", 
            f"确定要清除所有{history_type_name}历史记录吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            # 保存当前选中的项
            current_text = combo_box.currentText()
            
            # 清除下拉框和历史记录
            combo_box.clear()
            self.save_directory_history(key, [])
            
            # 如果有当前文本，重新添加
            if current_text:
                combo_box.addItem(current_text)
                combo_box.setCurrentText(current_text)
            
            return True
        
        return False
    
    def setup_combo_box_with_history(self, combo_box, key):
        """设置下拉框并加载历史记录
        
        Args:
            combo_box: 目标下拉框组件
            key: 历史记录的键名
        """
        # 设置为可编辑
        combo_box.setEditable(True)
        combo_box.setSizePolicy(combo_box.sizePolicy().horizontalPolicy(), 
                               combo_box.sizePolicy().verticalPolicy())
        combo_box.setMinimumWidth(300)
        
        # 加载历史记录
        history = self.load_directory_history(key)
        if history:
            combo_box.addItems(history) 