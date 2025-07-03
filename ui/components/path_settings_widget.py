"""
路径设置组件
负责源目录和目标目录的选择、历史记录管理等功能
"""
import os

from PySide6.QtCore import Signal, QSettings
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QCheckBox, QComboBox, QFileDialog, QMessageBox
)

import config


class PathSettingsWidget(QWidget):
    """路径设置组件"""
    
    # 信号定义
    source_dir_changed = Signal(str)  # 源目录改变
    target_dir_changed = Signal(str)  # 目标目录改变
    load_images_requested = Signal()  # 请求加载图像
    review_mode_toggled = Signal(bool)  # 审核模式切换
    group_by_id_toggled = Signal(bool)  # 按ID分组切换
    show_label_count_toggled = Signal(bool)  # 显示标签数切换
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # 初始化状态变量
        self.source_dir = ""
        self.target_dir = ""
        self.images_subdir = ""
        self.labels_subdir = ""
        self.is_review_mode = False
        self.group_by_id = True
        
        # 初始化历史记录设置
        self.settings = QSettings("YoloAnnotationTool", "DirectoryHistory")
        self.max_history_count = 5
        
        # 创建UI
        self._init_ui()
        
        # 连接信号
        self._connect_signals()
        
        # 设置默认路径
        self._set_default_paths()
    
    def _init_ui(self):
        """初始化UI"""
        # 创建主布局
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # 创建路径设置组
        path_group = self._create_path_group()
        layout.addWidget(path_group)
    
    def _create_path_group(self):
        """创建路径设置组"""
        path_group = QGroupBox("路径设置")
        path_layout = QVBoxLayout(path_group)
        
        # 源文件目录行
        source_layout = self._create_source_dir_layout()
        path_layout.addLayout(source_layout)
        
        # 目标目录行
        target_layout = self._create_target_dir_layout()
        path_layout.addLayout(target_layout)
        
        # 控制按钮行
        buttons_layout = self._create_buttons_layout()
        path_layout.addLayout(buttons_layout)
        
        return path_group
    
    def _create_source_dir_layout(self):
        """创建源目录选择布局"""
        layout = QHBoxLayout()
        
        # 标签
        label = QLabel("源文件目录:")
        label.setMinimumWidth(80)
        
        # 下拉框
        self.source_dir_combo = QComboBox()
        self._setup_combo_box_with_history(self.source_dir_combo, "source_directories")
        
        # 清除历史按钮
        clear_btn = self._create_clear_button("清除源目录历史记录")
        clear_btn.clicked.connect(self._clear_source_history)
        
        # 浏览按钮
        browse_btn = QPushButton("浏览...")
        browse_btn.clicked.connect(self._browse_source_dir)
        
        layout.addWidget(label)
        layout.addWidget(self.source_dir_combo, 1)
        layout.addWidget(clear_btn)
        layout.addWidget(browse_btn)
        
        return layout
    
    def _create_target_dir_layout(self):
        """创建目标目录选择布局"""
        layout = QHBoxLayout()
        
        # 标签
        label = QLabel("目标目录:")
        label.setMinimumWidth(80)
        
        # 下拉框
        self.target_dir_combo = QComboBox()
        self._setup_combo_box_with_history(self.target_dir_combo, "target_directories")
        
        # 清除历史按钮
        clear_btn = self._create_clear_button("清除目标目录历史记录")
        clear_btn.clicked.connect(self._clear_target_history)
        
        # 浏览按钮
        browse_btn = QPushButton("浏览...")
        browse_btn.clicked.connect(self._browse_target_dir)
        
        layout.addWidget(label)
        layout.addWidget(self.target_dir_combo, 1)
        layout.addWidget(clear_btn)
        layout.addWidget(browse_btn)
        
        return layout
    
    def _create_buttons_layout(self):
        """创建按钮控制布局"""
        layout = QHBoxLayout()
        
        # 按ID分组复选框
        self.group_by_id_checkbox = QCheckBox("按ID分组")
        self.group_by_id_checkbox.setChecked(True)
        
        # 显示标签数复选框
        self.show_label_count_checkbox = QCheckBox("显示标签数")
        self.show_label_count_checkbox.setChecked(False)
        
        # 加载按钮
        load_btn = QPushButton("加载图像")
        load_btn.setMinimumHeight(35)
        load_btn.setStyleSheet("QPushButton { font-weight: bold; }")
        load_btn.clicked.connect(self.load_images_requested.emit)
        
        # 审核模式切换按钮
        self.review_mode_btn = QPushButton("标注模式 (保留源文件)")
        self.review_mode_btn.setCheckable(True)
        self.review_mode_btn.setMinimumHeight(35)
        self._update_review_mode_button_style()
        
        layout.addWidget(self.group_by_id_checkbox)
        layout.addWidget(self.show_label_count_checkbox)
        layout.addStretch()
        layout.addWidget(load_btn)
        layout.addWidget(self.review_mode_btn)
        layout.addStretch()
        
        return layout
    
    def _create_clear_button(self, tooltip):
        """创建清除历史记录按钮"""
        btn = QPushButton("×")
        btn.setFixedSize(24, 24)
        btn.setToolTip(tooltip)
        btn.setStyleSheet("""
            QPushButton {
                font-size: 14px;
                font-weight: bold;
                color: #666;
                background-color: #f0f0f0;
                border: 1px solid #ccc;
                border-radius: 12px;
            }
            QPushButton:hover {
                background-color: #e0e0e0;
                color: #333;
            }
            QPushButton:pressed {
                background-color: #d0d0d0;
            }
        """)
        return btn
    
    def _connect_signals(self):
        """连接信号"""
        # 目录改变信号
        self.source_dir_combo.currentTextChanged.connect(self._on_source_dir_changed)
        self.source_dir_combo.activated.connect(self._on_source_dir_activated)
        
        self.target_dir_combo.currentTextChanged.connect(self._on_target_dir_changed)
        self.target_dir_combo.activated.connect(self._on_target_dir_activated)
        
        # 复选框信号
        self.group_by_id_checkbox.toggled.connect(self._on_group_by_id_toggled)
        self.show_label_count_checkbox.toggled.connect(self._on_show_label_count_toggled)
        
        # 审核模式按钮信号
        self.review_mode_btn.clicked.connect(self._on_review_mode_toggled)
    
    def _on_source_dir_changed(self, text):
        """处理源目录改变"""
        self.source_dir = text.strip()
        
        # 自动检测子目录
        if self.source_dir and os.path.exists(self.source_dir):
            images_dir, labels_dir = self._get_images_and_labels_dirs(self.source_dir)
            if images_dir and labels_dir:
                self.images_subdir = images_dir
                self.labels_subdir = labels_dir
        
        self.source_dir_changed.emit(self.source_dir)
    
    def _on_target_dir_changed(self, text):
        """处理目标目录改变"""
        self.target_dir = text.strip()
        self.target_dir_changed.emit(self.target_dir)
    
    def _on_source_dir_activated(self, index):
        """处理源目录用户选择"""
        selected_dir = self.source_dir_combo.itemText(index)
        if selected_dir and os.path.exists(selected_dir):
            self._add_to_history(self.source_dir_combo, selected_dir, "source_directories")
    
    def _on_target_dir_activated(self, index):
        """处理目标目录用户选择"""
        selected_dir = self.target_dir_combo.itemText(index)
        if selected_dir and os.path.exists(selected_dir):
            self._add_to_history(self.target_dir_combo, selected_dir, "target_directories")
    
    def _on_group_by_id_toggled(self, checked):
        """处理按ID分组切换"""
        self.group_by_id = checked
        self.group_by_id_toggled.emit(checked)
    
    def _on_show_label_count_toggled(self, checked):
        """处理显示标签数切换"""
        self.show_label_count_toggled.emit(checked)
    
    def _on_review_mode_toggled(self):
        """处理审核模式切换"""
        self.is_review_mode = not self.is_review_mode
        self._update_review_mode_button_style()
        self.review_mode_toggled.emit(self.is_review_mode)
    
    def _clear_source_history(self):
        """清除源目录历史记录"""
        self._clear_history(self.source_dir_combo, "source_directories", "源目录")
    
    def _clear_target_history(self):
        """清除目标目录历史记录"""
        self._clear_history(self.target_dir_combo, "target_directories", "目标目录")
    
    def _browse_source_dir(self):
        """浏览源目录"""
        current_dir = self.source_dir_combo.currentText() or os.path.expanduser("~")
        directory = QFileDialog.getExistingDirectory(
            self, "选择源文件目录", current_dir
        )
        if directory:
            self.source_dir = directory
            self._add_to_history(self.source_dir_combo, directory, "source_directories")
            
            # 自动检测子目录
            images_dir, labels_dir = self._get_images_and_labels_dirs(directory)
            if images_dir and labels_dir:
                self.images_subdir = images_dir
                self.labels_subdir = labels_dir
            else:
                self._show_directory_structure_warning()
    
    def _browse_target_dir(self):
        """浏览目标目录"""
        current_dir = self.target_dir_combo.currentText() or os.path.expanduser("~")
        directory = QFileDialog.getExistingDirectory(
            self, "选择目标目录", current_dir
        )
        if directory:
            self.target_dir = directory
            self._add_to_history(self.target_dir_combo, directory, "target_directories")
    
    def _get_images_and_labels_dirs(self, source_dir):
        """获取图像和标签子目录"""
        images_dir = None
        labels_dir = None
        
        # 模式1: 检查"images"和"labels"子文件夹
        potential_images_dir = os.path.join(source_dir, "images")
        potential_labels_dir = os.path.join(source_dir, "labels")
        
        if os.path.isdir(potential_images_dir):
            images_dir = potential_images_dir
        if os.path.isdir(potential_labels_dir):
            labels_dir = potential_labels_dir
        
        # 如果模式1成功，直接返回
        if images_dir and labels_dir:
            return images_dir, labels_dir
        
        # 模式2: 检查"original_snaps"和"original_snaps_labels"模式
        potential_images_dir = os.path.join(source_dir, "original_snaps")
        potential_labels_dir = os.path.join(source_dir, "original_snaps_labels")
        
        if os.path.isdir(potential_images_dir):
            images_dir = potential_images_dir
        if os.path.isdir(potential_labels_dir):
            labels_dir = potential_labels_dir
        
        return images_dir, labels_dir
    
    def _show_directory_structure_warning(self):
        """显示目录结构警告"""
        QMessageBox.warning(
            self, 
            "未找到有效目录结构", 
            "未在选择的目录中找到有效的图像和标签子文件夹。\n\n"
            "支持的目录结构:\n"
            "1. [选择的目录]/images 和 [选择的目录]/labels\n"
            "2. [选择的目录]/original_snaps 和 [选择的目录]/original_snaps_labels\n\n"
            "请检查目录结构是否符合上述模式。"
        )
    
    def _update_review_mode_button_style(self):
        """更新审核模式按钮样式"""
        if self.is_review_mode:
            self.review_mode_btn.setText("审核模式 (删除源文件)")
            self.review_mode_btn.setStyleSheet("""
                QPushButton {
                    background-color: #dc3545;
                    color: white;
                    font-weight: bold;
                    border: 2px solid #dc3545;
                    border-radius: 5px;
                    padding: 5px 10px;
                }
                QPushButton:hover {
                    background-color: #c82333;
                    border-color: #c82333;
                }
                QPushButton:pressed {
                    background-color: #a71e2a;
                    border-color: #a71e2a;
                }
            """)
        else:
            self.review_mode_btn.setText("标注模式 (保留源文件)")
            self.review_mode_btn.setStyleSheet("""
                QPushButton {
                    background-color: #28a745;
                    color: white;
                    font-weight: bold;
                    border: 2px solid #28a745;
                    border-radius: 5px;
                    padding: 5px 10px;
                }
                QPushButton:hover {
                    background-color: #218838;
                    border-color: #218838;
                }
                QPushButton:pressed {
                    background-color: #1e7e34;
                    border-color: #1e7e34;
                }
            """)
    
    def _set_default_paths(self):
        """设置默认路径"""
        # 设置默认源目录
        if config.DEFAULT_SOURCE_DIR and self.source_dir_combo.count() == 0:
            self.source_dir = config.DEFAULT_SOURCE_DIR
            self.source_dir_combo.addItem(self.source_dir)
            self.source_dir_combo.setCurrentText(self.source_dir)
            self._add_to_history(self.source_dir_combo, self.source_dir, "source_directories")
        elif self.source_dir_combo.count() > 0:
            self.source_dir = self.source_dir_combo.itemText(0)
            self.source_dir_combo.setCurrentText(self.source_dir)
        
        # 设置默认目标目录
        if config.DEFAULT_TARGET_DIR and self.target_dir_combo.count() == 0:
            self.target_dir = config.DEFAULT_TARGET_DIR
            self.target_dir_combo.addItem(self.target_dir)
            self.target_dir_combo.setCurrentText(self.target_dir)
            self._add_to_history(self.target_dir_combo, self.target_dir, "target_directories")
        elif self.target_dir_combo.count() > 0:
            self.target_dir = self.target_dir_combo.itemText(0)
            self.target_dir_combo.setCurrentText(self.target_dir)
        
        # 自动检测子目录
        if self.source_dir:
            images_dir, labels_dir = self._get_images_and_labels_dirs(self.source_dir)
            if images_dir:
                self.images_subdir = images_dir
            if labels_dir:
                self.labels_subdir = labels_dir
    
    # 公共接口方法
    def get_source_dir(self):
        """获取源目录"""
        return self.source_dir
    
    def get_target_dir(self):
        """获取目标目录"""
        return self.target_dir
    
    def get_images_subdir(self):
        """获取图像子目录"""
        return self.images_subdir
    
    def get_labels_subdir(self):
        """获取标签子目录"""
        return self.labels_subdir
    
    def is_review_mode_enabled(self):
        """是否启用审核模式"""
        return self.is_review_mode
    
    def is_group_by_id_enabled(self):
        """是否启用按ID分组"""
        return self.group_by_id
    
    def validate_paths(self):
        """验证路径有效性"""
        if not self.source_dir or not os.path.exists(self.source_dir):
            return False, "请选择有效的源文件目录"
        
        if not self.images_subdir or not os.path.exists(self.images_subdir):
            return False, "在源目录中未找到images子文件夹"
        
        if not self.labels_subdir or not os.path.exists(self.labels_subdir):
            return False, "在源目录中未找到labels子文件夹"
        
        return True, ""
    
    # 历史记录管理私有方法
    def _load_directory_history(self, key):
        """加载目录历史记录"""
        history = self.settings.value(key, [])
        if isinstance(history, str):
            history = [history] if history else []
        elif not isinstance(history, list):
            history = []
        return history
    
    def _save_directory_history(self, key, history):
        """保存目录历史记录"""
        if len(history) > self.max_history_count:
            history = history[:self.max_history_count]
        self.settings.setValue(key, history)
        self.settings.sync()
    
    def _add_to_history(self, combo_box, directory, key):
        """添加目录到历史记录"""
        if not directory or not os.path.exists(directory):
            return
        
        current_items = [combo_box.itemText(i) for i in range(combo_box.count())]
        
        if directory in current_items:
            current_items.remove(directory)
        
        current_items.insert(0, directory)
        
        if len(current_items) > self.max_history_count:
            current_items = current_items[:self.max_history_count]
        
        combo_box.clear()
        combo_box.addItems(current_items)
        combo_box.setCurrentText(directory)
        
        self._save_directory_history(key, current_items)
    
    def _clear_history(self, combo_box, key, history_type_name):
        """清除历史记录"""
        reply = QMessageBox.question(
            self, "确认清除", 
            f"确定要清除所有{history_type_name}历史记录吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            current_text = combo_box.currentText()
            combo_box.clear()
            self._save_directory_history(key, [])
            
            if current_text:
                combo_box.addItem(current_text)
                combo_box.setCurrentText(current_text)
            
            return True
        return False
    
    def _setup_combo_box_with_history(self, combo_box, key):
        """设置下拉框并加载历史记录"""
        combo_box.setEditable(True)
        combo_box.setSizePolicy(combo_box.sizePolicy().horizontalPolicy(), 
                               combo_box.sizePolicy().verticalPolicy())
        combo_box.setMinimumWidth(300)
        
        history = self._load_directory_history(key)
        if history:
            combo_box.addItems(history) 