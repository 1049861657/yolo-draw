"""
YOLO模型设置对话框
允许用户选择要使用的YOLO模型
"""
import os
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, 
    QPushButton, QGroupBox, QMessageBox, QFrame, QSizePolicy
)

import config
from utils.yolo_model_manager import YoloModelManager


class ModelSettingsDialog(QDialog):
    """YOLO模型设置对话框"""
    
    # 信号定义
    model_changed = Signal(str)  # 模型更改信号
    
    def __init__(self, parent=None):
        """初始化对话框"""
        super().__init__(parent)
        
        self.model_manager = YoloModelManager()
        self.current_model = self.model_manager.get_selected_model()
        self.available_models = self.model_manager.get_available_models()
        
        self._init_ui()
        self._load_current_settings()
    
    def _init_ui(self):
        """初始化UI"""
        self.setWindowTitle("YOLO模型设置")
        self.setModal(True)
        self.setFixedSize(400, 250)
        
        # 主布局
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(20, 20, 20, 20)
        
        # 标题
        title_label = QLabel("选择YOLO预测模型")
        title_label.setStyleSheet("""
            QLabel {
                font-size: 16px;
                font-weight: bold;
                color: #2c3e50;
                padding: 5px 0;
            }
        """)
        main_layout.addWidget(title_label)
        
        # 分隔线
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        separator.setStyleSheet("QFrame { color: #bdc3c7; }")
        main_layout.addWidget(separator)
        
        # 模型选择组
        model_group = QGroupBox("可用模型")
        model_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #bdc3c7;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
                color: #34495e;
            }
        """)
        model_layout = QVBoxLayout(model_group)
        model_layout.setSpacing(10)
        
        # 模型选择下拉框
        model_selection_layout = QHBoxLayout()
        
        model_label = QLabel("选择模型:")
        model_label.setMinimumWidth(80)
        model_label.setStyleSheet("QLabel { font-weight: normal; }")
        
        self.model_combo = QComboBox()
        self.model_combo.setMinimumHeight(30)
        self.model_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.model_combo.setStyleSheet("""
            QComboBox {
                border: 1px solid #bdc3c7;
                border-radius: 4px;
                padding: 5px 10px;
                background-color: white;
            }
            QComboBox:hover {
                border-color: #3498db;
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            QComboBox::down-arrow {
                image: none;
                border: 2px solid #7f8c8d;
                width: 6px;
                height: 6px;
                border-top: none;
                border-left: none;
                margin-right: 5px;
            }
        """)
        
        # 填充可用模型
        if self.available_models:
            self.model_combo.addItems(self.available_models)
        else:
            self.model_combo.addItem("未找到模型文件")
            self.model_combo.setEnabled(False)
        
        model_selection_layout.addWidget(model_label)
        model_selection_layout.addWidget(self.model_combo)
        
        model_layout.addLayout(model_selection_layout)
        
        # 模型信息显示
        self.model_info_label = QLabel()
        self.model_info_label.setStyleSheet("""
            QLabel {
                color: #7f8c8d;
                font-size: 12px;
                padding: 5px;
                background-color: #ecf0f1;
                border-radius: 4px;
            }
        """)
        self.model_info_label.setWordWrap(True)
        model_layout.addWidget(self.model_info_label)
        
        main_layout.addWidget(model_group)
        
        # 弹簧，将按钮推到底部
        main_layout.addStretch()
        
        # 按钮布局
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)
        
        # 取消按钮
        self.cancel_button = QPushButton("取消")
        self.cancel_button.setMinimumHeight(35)
        self.cancel_button.setStyleSheet("""
            QPushButton {
                background-color: #95a5a6;
                color: white;
                border: none;
                border-radius: 6px;
                font-weight: bold;
                padding: 5px 15px;
            }
            QPushButton:hover {
                background-color: #7f8c8d;
            }
            QPushButton:pressed {
                background-color: #6c7b7d;
            }
        """)
        self.cancel_button.clicked.connect(self.reject)
        
        # 确定按钮
        self.ok_button = QPushButton("确定")
        self.ok_button.setMinimumHeight(35)
        self.ok_button.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                border-radius: 6px;
                font-weight: bold;
                padding: 5px 15px;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
            QPushButton:pressed {
                background-color: #21618c;
            }
        """)
        self.ok_button.clicked.connect(self._apply_settings)
        self.ok_button.setDefault(True)
        
        # 如果没有可用模型，禁用确定按钮
        if not self.available_models:
            self.ok_button.setEnabled(False)
        
        button_layout.addStretch()
        button_layout.addWidget(self.cancel_button)
        button_layout.addWidget(self.ok_button)
        
        main_layout.addLayout(button_layout)
        
        # 连接信号
        self.model_combo.currentTextChanged.connect(self._update_model_info)
    
    def _load_current_settings(self):
        """加载当前设置"""
        if self.current_model and self.current_model in self.available_models:
            index = self.available_models.index(self.current_model)
            self.model_combo.setCurrentIndex(index)
        
        self._update_model_info()
    
    def _update_model_info(self):
        """更新模型信息显示"""
        if not self.available_models:
            self.model_info_label.setText("未找到任何.pt模型文件，请将模型文件放置到pt目录下")
            return
        
        selected_model = self.model_combo.currentText()
        if selected_model:
            model_info = self.model_manager.get_model_info(selected_model)
            if model_info:
                info_text = f"模型文件: {model_info['name']}\n"
                info_text += f"文件大小: {model_info['size_mb']:.1f} MB\n"
                info_text += f"文件路径: {model_info['path']}"
                
                self.model_info_label.setText(info_text)
            else:
                self.model_info_label.setText(f"模型文件不存在: {selected_model}")
    
    def _apply_settings(self):
        """应用设置"""
        if not self.available_models:
            QMessageBox.warning(self, "警告", "没有可用的模型文件")
            return
        
        selected_model = self.model_combo.currentText()
        
        # 检查模型文件是否存在
        if not self.model_manager.model_exists(selected_model):
            model_path = self.model_manager.get_model_path(selected_model)
            QMessageBox.critical(self, "错误", f"模型文件不存在: {model_path}")
            return
        
        # 保存设置
        if self.model_manager.set_selected_model(selected_model):
            # 如果模型发生变化，发射信号
            if selected_model != self.current_model:
                self.model_changed.emit(selected_model)
            
            self.accept()
        else:
            QMessageBox.critical(self, "错误", "保存模型设置失败")
    
    def get_selected_model(self):
        """获取选择的模型"""
        if self.available_models:
            return self.model_combo.currentText()
        return None 