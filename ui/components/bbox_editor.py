"""
标注框编辑组件
负责标注框的创建、编辑、删除和列表显示
"""
import os
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QGroupBox, QVBoxLayout, QHBoxLayout, QPushButton, QTreeWidget, 
    QTreeWidgetItem, QMenu, QMessageBox
)
from PySide6.QtGui import QColor

import config


class BBoxEditorWidget(QGroupBox):
    """标注框编辑组件"""
    
    # 信号定义
    bbox_selected = Signal(int)  # 标注框被选中信号 (索引)
    bbox_class_changed = Signal(int, int)  # 标注框类别改变信号 (索引, 新类别ID)
    bbox_deleted = Signal(int)  # 标注框被删除信号 (索引)
    add_bbox_requested = Signal()  # 请求添加标注框信号
    
    def __init__(self, parent=None):
        """初始化标注框编辑组件"""
        super().__init__("标注框列表", parent)
        
        # 初始化状态变量
        self.ship_types = config.get_ship_types()
        self.current_labels = []
        self.selected_bbox_index = -1
        
        # 创建UI
        self._init_ui()
        
        # 连接信号
        self._connect_signals()
    
    def _init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # 创建"添加标注框"按钮
        self.add_bbox_button = QPushButton("添加标注框(Q)")
        self.add_bbox_button.setStyleSheet("background-color: #3399FF; color: white; font-weight: bold;")
        self.add_bbox_button.setMinimumWidth(120)
        self.add_bbox_button.setMaximumWidth(150)
        
        # 创建标注框列表控件
        self.bbox_list = QTreeWidget()
        self.bbox_list.setHeaderLabels(["ID", "类别"])
        self.bbox_list.setMinimumWidth(120)
        self.bbox_list.setMaximumWidth(150)
        self.bbox_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        
        # 调整列宽度比例：ID列较窄，类别列较宽
        self.bbox_list.setColumnWidth(0, 40)  # ID列宽度固定为40像素
        
        # 添加组件到布局
        layout.addWidget(self.add_bbox_button)
        layout.addWidget(self.bbox_list)
    
    def _connect_signals(self):
        """连接信号"""
        self.add_bbox_button.clicked.connect(self.on_add_bbox_clicked)
        self.bbox_list.itemClicked.connect(self.on_bbox_item_clicked)
        self.bbox_list.customContextMenuRequested.connect(self.on_bbox_context_menu)
    
    def on_add_bbox_clicked(self):
        """处理添加标注框按钮点击"""
        self.add_bbox_requested.emit()
    
    def on_bbox_item_clicked(self, item, column):
        """处理标注框列表项的点击事件"""
        if not item:
            return
        
        # 获取点击项的标签索引
        bbox_index = item.data(0, Qt.ItemDataRole.UserRole)
        if bbox_index is not None:
            self.selected_bbox_index = bbox_index
            self.bbox_selected.emit(bbox_index)
    
    def on_bbox_context_menu(self, position):
        """处理标注框列表的右键菜单事件"""
        # 获取当前选中项
        item = self.bbox_list.itemAt(position)
        if not item:
            return
        
        # 获取标签索引
        bbox_index = item.data(0, Qt.ItemDataRole.UserRole)
        if bbox_index is None:
            return
        
        # 创建右键菜单
        context_menu = self.create_context_menu_for_bbox(bbox_index)
        
        # 显示菜单
        if context_menu:
            context_menu.exec(self.bbox_list.viewport().mapToGlobal(position))
    
    def create_context_menu_for_bbox(self, bbox_index):
        """为边界框创建右键菜单"""
        # 确保有标签数据
        if bbox_index < 0 or bbox_index >= len(self.current_labels):
            return None
        
        # 创建菜单
        menu = QMenu(self)
        
        # 获取当前类别ID
        current_class_id = int(self.current_labels[bbox_index][0])
        
        # 添加船舶类型选项
        for key, value in self.ship_types.items():
            action = menu.addAction(value)
            action.setData(int(key))
            
            # 标记当前选中的类型
            if int(key) == current_class_id:
                # 使用粗体字体表示当前选中的类型
                font = action.font()
                font.setBold(True)
                action.setFont(font)
            
            # 连接操作信号
            action.triggered.connect(lambda checked, k=key, b=bbox_index: self.change_bbox_class(b, int(k)))
        
        # 添加分隔线
        menu.addSeparator()
        
        # 添加删除选项
        delete_action = menu.addAction("删除此边界框")
        delete_action.triggered.connect(lambda: self.delete_bbox(bbox_index))
        
        return menu
    
    def change_bbox_class(self, bbox_index, new_class_id):
        """更改边界框的类别"""
        if 0 <= bbox_index < len(self.current_labels):
            self.bbox_class_changed.emit(bbox_index, new_class_id)
    
    def delete_bbox(self, bbox_index):
        """删除边界框"""
        if 0 <= bbox_index < len(self.current_labels):
            self.bbox_deleted.emit(bbox_index)
    
    def update_bbox_list(self, labels):
        """更新标注框列表
        
        Args:
            labels: 标签数据列表
        """
        self.current_labels = labels
        self.bbox_list.clear()
        
        # 检查是否有有效的标签数据
        if not labels:
            return
        
        # 将每个标签添加到列表中
        for i, label in enumerate(labels):
            if len(label) == 5:
                class_id = int(label[0])
                class_name = self.ship_types.get(str(class_id), f"未知类型({class_id})")
                
                # 创建列表项
                item = QTreeWidgetItem()
                item.setText(0, str(i))  # ID列
                item.setText(1, class_name)  # 类别列
                
                # 根据类别设置背景颜色
                color_idx = class_id % len(config.BOX_COLORS)
                color = config.BOX_COLORS[color_idx]
                item.setBackground(1, QColor(color))
                
                # 设置文本颜色为白色以增强可读性
                item.setForeground(1, QColor("white"))
                
                # 使ID列文本居中对齐
                item.setTextAlignment(0, Qt.AlignmentFlag.AlignCenter)
                
                # 将标签索引存储在项的数据中，以便于后续访问
                item.setData(0, Qt.ItemDataRole.UserRole, i)
                
                # 添加项到列表
                self.bbox_list.addTopLevelItem(item)
        
        # 保持ID列宽度固定
        self.bbox_list.setColumnWidth(0, 40)
        
        # 让类别列自动调整以填充剩余空间
        self.bbox_list.setColumnWidth(1, self.bbox_list.width() - 45)  # 留一点边距
    
    def set_selected_bbox(self, bbox_index):
        """设置选中的标注框"""
        self.selected_bbox_index = bbox_index
        
        # 在列表中高亮显示对应项
        for i in range(self.bbox_list.topLevelItemCount()):
            item = self.bbox_list.topLevelItem(i)
            item_index = item.data(0, Qt.ItemDataRole.UserRole)
            if item_index == bbox_index:
                self.bbox_list.setCurrentItem(item)
                break
    
    def get_selected_bbox_index(self):
        """获取当前选中的标注框索引"""
        return self.selected_bbox_index
    
    def clear_selection(self):
        """清除选择"""
        self.selected_bbox_index = -1
        self.bbox_list.clearSelection()
    
    def clear_bbox_list(self):
        """清空标注框列表"""
        self.bbox_list.clear()
        self.current_labels = []
        self.selected_bbox_index = -1
    
    def show_class_menu_for_bbox(self, bbox_index, global_pos):
        """为指定标注框显示类别选择菜单"""
        # 创建船舶类型选择菜单
        context_menu = self.create_context_menu_for_bbox(bbox_index)
        
        if context_menu:
            # 显示菜单
            context_menu.exec(global_pos) 