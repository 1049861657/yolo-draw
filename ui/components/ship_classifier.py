"""
船舶分类组件
负责船舶类型按钮和分类处理逻辑
"""
import os
import shutil
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QGroupBox, QVBoxLayout, QHBoxLayout, QGridLayout, QPushButton, 
    QLabel, QFrame, QMessageBox
)

import config
from models.yolo_label import YoloLabel
from utils import file_utils


class ShipClassifierWidget(QGroupBox):
    """船舶分类组件"""
    
    # 信号定义
    image_processed = Signal(str, str)  # 图像处理完成信号 (图像路径, 类别名称)
    image_discarded = Signal(str)  # 图像被丢弃信号 (图像路径)
    group_discarded = Signal(str)  # 组被丢弃信号 (组ID)
    auto_classify_requested = Signal()  # 请求自动分类信号
    ship_type_selected = Signal(int, str)  # 船舶类型被选中信号 (类别ID, 类别名称)
    discard_single_requested = Signal()  # 请求丢弃单个信号
    discard_group_requested = Signal()  # 请求丢弃整组信号
    
    def __init__(self, parent=None):
        """初始化船舶分类组件"""
        super().__init__("标签编辑", parent)
        
        # 初始化状态变量
        self.ship_types = config.get_ship_types()
        self.ship_type_buttons = {}
        self.target_dir = ""
        self.labels_subdir = ""
        self.is_review_mode = False
        self.group_by_id = True
        self.batch_mode = False  # 批量模式状态
        self.batch_count = 0     # 批量选择的数量
        
        # 创建UI
        self._init_ui()
        
        # 连接信号
        self._connect_signals()
    
    def _init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        
        # 添加说明标签
        self.instruction_label = QLabel("点击船舶类型按钮将直接标注并移动图像：")
        layout.addWidget(self.instruction_label)
        
        # 创建船舶类型按钮
        self._create_ship_type_buttons(layout)
        
        # 添加舍弃按钮和自动分类按钮
        self._add_action_buttons(layout)
    
    def _create_ship_type_buttons(self, parent_layout):
        """创建船舶类型按钮"""
        # 使用网格布局来排列按钮
        grid_layout = QGridLayout()
        
        # 定义每行最大按钮数
        buttons_per_row = 4
        
        # 为每种船舶类型创建按钮
        for i, (type_id, type_name) in enumerate(self.ship_types.items()):
            button = QPushButton(f"{type_id}: {type_name}")
            
            # 设置按钮的数据（船舶类型ID）
            button.setProperty("ship_type_id", type_id)
            
            # 计算按钮位置（行和列）
            row = i // buttons_per_row
            col = i % buttons_per_row
            
            # 添加到网格布局
            grid_layout.addWidget(button, row, col)
            
            # 保存按钮引用
            self.ship_type_buttons[type_id] = button
            
            # 连接点击事件
            button.clicked.connect(
                lambda checked, btn=button: self.on_ship_type_button_clicked(btn)
            )
        
        # 将网格布局添加到父布局
        parent_layout.addLayout(grid_layout)
    
    def _add_action_buttons(self, parent_layout):
        """添加操作按钮"""
        # 创建一个水平布局用于放置按钮
        buttons_layout = QHBoxLayout()
        buttons_layout.addStretch()
        
        # 创建"丢弃单个"按钮
        self.discard_single_button = QPushButton("丢弃单个")
        self.discard_single_button.setMinimumHeight(40)
        self.discard_single_button.setStyleSheet("background-color: #FF9955; color: white; font-weight: bold;")
        self.discard_single_button.clicked.connect(self.on_discard_single_clicked)
        
        # 创建舍弃按钮
        self.discard_button = QPushButton("丢弃整组")
        self.discard_button.setMinimumHeight(40)
        self.discard_button.setStyleSheet("background-color: #FF5555; color: white; font-weight: bold;")
        self.discard_button.clicked.connect(self.on_discard_group_clicked)
        
        # 创建"发送单个"按钮（之前的"自动分类"按钮）
        self.auto_classify_button = QPushButton("发送单个")
        self.auto_classify_button.setMinimumHeight(40)
        self.auto_classify_button.setStyleSheet("background-color: #55AA55; color: white; font-weight: bold;")
        self.auto_classify_button.clicked.connect(self.on_auto_classify_clicked)
        
        # 添加按钮到布局
        buttons_layout.addWidget(self.discard_single_button)
        buttons_layout.addWidget(self.discard_button)
        buttons_layout.addWidget(self.auto_classify_button)
        buttons_layout.addStretch()
        
        # 添加一个分隔行
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        
        # 添加到父布局
        parent_layout.addWidget(separator)
        parent_layout.addLayout(buttons_layout)
    
    def _connect_signals(self):
        """连接信号"""
        # 船舶类型按钮的信号已在创建时连接
        pass
    
    def on_ship_type_button_clicked(self, button):
        """处理船舶类型按钮点击事件"""
        # 获取按钮对应的船舶类型ID
        class_id = int(button.property("ship_type_id"))
        current_class_name = self.ship_types.get(str(class_id), '未知')
        
        # 发射信号，由主窗口处理具体的标注逻辑
        self.ship_type_selected.emit(class_id, current_class_name)
    
    def on_discard_single_clicked(self):
        """处理丢弃单个按钮点击"""
        self.discard_single_requested.emit()
    
    def on_discard_group_clicked(self):
        """处理丢弃整组按钮点击"""
        self.discard_group_requested.emit()
    
    def on_auto_classify_clicked(self):
        """处理自动分类按钮点击"""
        self.auto_classify_requested.emit()
    
    def set_target_dir(self, target_dir):
        """设置目标目录"""
        self.target_dir = target_dir
    
    def set_labels_subdir(self, labels_subdir):
        """设置标签子目录"""
        self.labels_subdir = labels_subdir
    
    def set_review_mode(self, is_review_mode):
        """设置审核模式"""
        self.is_review_mode = is_review_mode
    
    def set_group_by_id(self, group_by_id):
        """设置是否按ID分组"""
        self.group_by_id = group_by_id
        
        # 根据分组模式显示或隐藏"丢弃整组"按钮
        if group_by_id:
            self.discard_button.show()
        else:
            self.discard_button.hide()
    
    def set_batch_mode(self, is_batch_mode, batch_count=0):
        """设置批量模式
        
        Args:
            is_batch_mode: 是否为批量模式
            batch_count: 批量选择的数量
        """
        self.batch_mode = is_batch_mode
        self.batch_count = batch_count
        
        if is_batch_mode:
            # 批量模式：更新标题和按钮文本
            self.setTitle(f"批量操作 - 已选择 {batch_count} 项")
            self.instruction_label.setText(f"点击船舶类型按钮将批量标注并移动 {batch_count} 个图像：")
            
            # 更新按钮文本
            self.discard_single_button.setText(f"丢弃批量 ({batch_count})")
            # 在批量模式下，如果不是分组模式，隐藏"丢弃整组"按钮
            if not self.group_by_id:
                self.discard_button.hide()
            else:
                self.discard_button.setText(f"丢弃批量 ({batch_count})")
                self.discard_button.show()
            self.auto_classify_button.setText(f"发送批量 ({batch_count})")
        else:
            # 单个模式：恢复原始文本
            self.setTitle("标签编辑")
            self.instruction_label.setText("点击船舶类型按钮将直接标注并移动图像：")
            
            # 恢复按钮文本
            self.discard_single_button.setText("丢弃单个")
            if self.group_by_id:
                self.discard_button.setText("丢弃整组")
                self.discard_button.show()
            else:
                self.discard_button.hide()
            self.auto_classify_button.setText("发送单个") 