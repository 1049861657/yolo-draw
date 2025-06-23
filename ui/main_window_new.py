"""
新版主窗口UI模块 (PySide6版本)
使用组件化架构实现标注工具的界面和交互逻辑
"""
import os
import sys
import time
import json
from collections import deque
from PySide6.QtCore import Qt, QPoint, QTimer, QSettings
from PySide6.QtGui import QKeySequence, QShortcut, QCursor
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QFrame, QStatusBar, QFileDialog, QMessageBox,
    QGroupBox, QCheckBox, QComboBox
)

import config
from models.yolo_label import YoloLabel
from utils import file_utils
from utils.yolo_model_manager import YoloModelManager
from .components import (
    ImageListWidget, BBoxEditorWidget, ShipClassifierWidget, ImageViewerWidget, ModelSettingsDialog
)


class MainWindow(QMainWindow):
    """主窗口类，使用组件化架构实现标注工具的界面和交互逻辑"""
    
    def __init__(self):
        """初始化主窗口"""
        super().__init__()
        
        # 设置窗口标题和尺寸
        self.setWindowTitle(f"{config.APP_NAME} v{config.APP_VERSION}")
        self.resize(config.APP_WIDTH, config.APP_HEIGHT)
        
        # 初始化状态变量
        self._init_state_variables()
        
        # 初始化标注速度统计
        self._init_annotation_speed_tracking()
        
        # 初始化目录历史记录
        self._init_directory_history()
        
        # 创建UI组件
        self._init_ui_components()
        
        # 连接信号
        self._connect_signals()
        
        # 设置默认路径
        self._set_default_paths()
    
    def _init_state_variables(self):
        """初始化状态变量"""
        # 路径相关
        self.source_dir = ""
        self.images_subdir = ""
        self.labels_subdir = ""
        self.target_dir = ""
        
        # 图像相关
        self.image_files = []
        self.current_image_idx = -1
        
        # 模式和分组相关
        self.is_review_mode = False
        self.group_by_id = True
        
        # 船舶类型
        self.ship_types = config.get_ship_types()
    
    def _init_annotation_speed_tracking(self):
        """初始化标注速度统计"""
        # 标注时间记录队列（最多保存最近20次标注的时间）
        self.annotation_times = deque(maxlen=20)
        
        # 标注计数器
        self.total_annotations = 0
        self.session_start_time = time.time()
        
        # 创建定时器用于更新速度显示
        self.speed_update_timer = QTimer()
        self.speed_update_timer.timeout.connect(self._update_speed_display)
        self.speed_update_timer.start(1000)  # 每秒更新一次
    
    def _init_directory_history(self):
        """初始化目录历史记录功能"""
        # 使用QSettings来持久化存储历史记录
        self.settings = QSettings("YoloAnnotationTool", "DirectoryHistory")
        
        # 最大历史记录数量
        self.max_history_count = 5
    
    def _load_directory_history(self, key):
        """加载目录历史记录"""
        history = self.settings.value(key, [])
        if isinstance(history, str):
            # 兼容旧版本，如果是字符串则转换为列表
            history = [history] if history else []
        elif not isinstance(history, list):
            history = []
        return history
    
    def _save_directory_history(self, key, history):
        """保存目录历史记录"""
        # 确保历史记录不超过最大数量
        if len(history) > self.max_history_count:
            history = history[:self.max_history_count]
        
        self.settings.setValue(key, history)
        self.settings.sync()  # 立即同步到磁盘
    
    def _add_to_history(self, combo_box, directory, key):
        """添加目录到历史记录"""
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
        self._save_directory_history(key, current_items)
    
    def _on_source_dir_changed(self, text):
        """处理源目录下拉框文本变化"""
        self.source_dir = text.strip()
        
        # 自动检测images和labels子文件夹
        if self.source_dir and os.path.exists(self.source_dir):
            images_dir, labels_dir = self.get_images_and_labels_dirs(self.source_dir)
            if images_dir and labels_dir:
                self.images_subdir = images_dir
                self.labels_subdir = labels_dir
                self.status_bar.showMessage(f"已找到图像目录: {os.path.basename(images_dir)} 和标签目录: {os.path.basename(labels_dir)}")
    
    def _on_target_dir_changed(self, text):
        """处理目标目录下拉框文本变化"""
        self.target_dir = text.strip()
    
    def _clear_source_history(self):
        """清除源目录历史记录"""
        reply = QMessageBox.question(
            self, "确认清除", 
            "确定要清除所有源目录历史记录吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            # 保存当前选中的项
            current_text = self.source_dir_combo.currentText()
            
            # 清除下拉框和历史记录
            self.source_dir_combo.clear()
            self._save_directory_history("source_directories", [])
            
            # 如果有当前文本，重新添加
            if current_text:
                self.source_dir_combo.addItem(current_text)
                self.source_dir_combo.setCurrentText(current_text)
            
            self.status_bar.showMessage("已清除源目录历史记录")
    
    def _clear_target_history(self):
        """清除目标目录历史记录"""
        reply = QMessageBox.question(
            self, "确认清除", 
            "确定要清除所有目标目录历史记录吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            # 保存当前选中的项
            current_text = self.target_dir_combo.currentText()
            
            # 清除下拉框和历史记录
            self.target_dir_combo.clear()
            self._save_directory_history("target_directories", [])
            
            # 如果有当前文本，重新添加
            if current_text:
                self.target_dir_combo.addItem(current_text)
                self.target_dir_combo.setCurrentText(current_text)
            
            self.status_bar.showMessage("已清除目标目录历史记录")
    
    def _init_ui_components(self):
        """初始化UI组件"""
        # 创建中央窗口部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 创建主布局
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(5)
        
        # 路径设置区域
        path_group = self._create_path_settings()
        main_layout.addWidget(path_group)
        
        # 创建内容区布局
        content_layout = QHBoxLayout()
        content_layout.setSpacing(5)
        
        # 图像列表组件
        self.image_list_widget = ImageListWidget()
        
        # 图像查看器组件
        self.image_viewer_widget = ImageViewerWidget()
        
        # 标注框编辑组件
        self.bbox_editor_widget = BBoxEditorWidget()
        
        # 创建右侧布局（图像查看器 + 标注框编辑器）
        right_layout = QHBoxLayout()
        right_layout.addWidget(self.image_viewer_widget, 3)
        right_layout.addWidget(self.bbox_editor_widget, 0)
        
        # 添加到内容布局
        content_layout.addWidget(self.image_list_widget, 1)
        content_layout.addLayout(right_layout, 4)
        
        main_layout.addLayout(content_layout, 4)
        
        # 船舶分类组件
        self.ship_classifier_widget = ShipClassifierWidget()
        main_layout.addWidget(self.ship_classifier_widget, 1)
        
        # 创建状态栏
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        
        # 创建模型管理器
        self.model_manager = YoloModelManager()
        
        # 创建模型设置按钮
        self.model_settings_button = QPushButton("⚙️ 模型设置")
        self.model_settings_button.setFixedHeight(28)
        self.model_settings_button.setStyleSheet("""
            QPushButton {
                background-color: #34495e;
                color: white;
                font-size: 12px;
                font-weight: bold;
                border: 1px solid #2c3e50;
                border-radius: 4px;
                padding: 2px 8px;
            }
            QPushButton:hover {
                background-color: #2c3e50;
                border-color: #34495e;
            }
            QPushButton:pressed {
                background-color: #1e2832;
            }
        """)
        self.model_settings_button.clicked.connect(self.show_model_settings)
        self.status_bar.addPermanentWidget(self.model_settings_button)
        
        # 创建标注速度显示标签
        self.speed_label = QLabel("🚀 标注速度: 0.0 图片/秒")
        self.speed_label.setStyleSheet("""
            QLabel {
                color: #2E8B57;
                font-weight: bold;
                padding: 2px 8px;
                border: 1px solid #2E8B57;
                border-radius: 3px;
                background-color: rgba(46, 139, 87, 0.1);
            }
        """)
        self.status_bar.addPermanentWidget(self.speed_label)
        
        self.status_bar.showMessage("就绪")
    
    def _create_path_settings(self):
        """创建路径设置区域"""
        path_group = QGroupBox("路径设置")
        path_layout = QVBoxLayout(path_group)
        
        # 源文件目录
        source_dir_layout = QHBoxLayout()
        source_dir_label = QLabel("源文件目录:")
        source_dir_label.setMinimumWidth(80)
        
        # 使用可编辑的下拉框
        self.source_dir_combo = QComboBox()
        self.source_dir_combo.setEditable(True)
        self.source_dir_combo.setSizePolicy(self.source_dir_combo.sizePolicy().horizontalPolicy(), 
                                           self.source_dir_combo.sizePolicy().verticalPolicy())
        self.source_dir_combo.setMinimumWidth(300)
        
        # 加载历史记录
        source_history = self._load_directory_history("source_directories")
        if source_history:
            self.source_dir_combo.addItems(source_history)
        
        # 连接信号
        self.source_dir_combo.currentTextChanged.connect(self._on_source_dir_changed)
        
        # 清除历史按钮（小按钮）
        clear_source_btn = QPushButton("×")
        clear_source_btn.setFixedSize(24, 24)
        clear_source_btn.setToolTip("清除源目录历史记录")
        clear_source_btn.clicked.connect(self._clear_source_history)
        clear_source_btn.setStyleSheet("""
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
        
        source_dir_btn = QPushButton("浏览...")
        source_dir_btn.clicked.connect(self.browse_source_dir)
        source_dir_layout.addWidget(source_dir_label)
        source_dir_layout.addWidget(self.source_dir_combo, 1)
        source_dir_layout.addWidget(clear_source_btn)
        source_dir_layout.addWidget(source_dir_btn)
        path_layout.addLayout(source_dir_layout)
        
        # 目标目录
        target_dir_layout = QHBoxLayout()
        target_dir_label = QLabel("目标目录:")
        target_dir_label.setMinimumWidth(80)
        
        # 使用可编辑的下拉框
        self.target_dir_combo = QComboBox()
        self.target_dir_combo.setEditable(True)
        self.target_dir_combo.setSizePolicy(self.target_dir_combo.sizePolicy().horizontalPolicy(), 
                                           self.target_dir_combo.sizePolicy().verticalPolicy())
        self.target_dir_combo.setMinimumWidth(300)
        
        # 加载历史记录
        target_history = self._load_directory_history("target_directories")
        if target_history:
            self.target_dir_combo.addItems(target_history)
        
        # 连接信号
        self.target_dir_combo.currentTextChanged.connect(self._on_target_dir_changed)
        
        # 清除历史按钮（小按钮）
        clear_target_btn = QPushButton("×")
        clear_target_btn.setFixedSize(24, 24)
        clear_target_btn.setToolTip("清除目标目录历史记录")
        clear_target_btn.clicked.connect(self._clear_target_history)
        clear_target_btn.setStyleSheet("""
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
        
        target_dir_btn = QPushButton("浏览...")
        target_dir_btn.clicked.connect(self.browse_target_dir)
        target_dir_layout.addWidget(target_dir_label)
        target_dir_layout.addWidget(self.target_dir_combo, 1)
        target_dir_layout.addWidget(clear_target_btn)
        target_dir_layout.addWidget(target_dir_btn)
        path_layout.addLayout(target_dir_layout)
        
        # 加载按钮和选项
        buttons_layout = QHBoxLayout()
        
        # 按ID分组勾选框
        self.group_by_id_checkbox = QCheckBox("按ID分组")
        self.group_by_id_checkbox.setChecked(True)
        self.group_by_id_checkbox.toggled.connect(self.on_group_by_id_toggle)
        
        # 显示标签数勾选框
        self.show_label_count_checkbox = QCheckBox("显示标签数")
        self.show_label_count_checkbox.setChecked(False)  # 默认关闭
        self.show_label_count_checkbox.toggled.connect(self.on_show_label_count_toggle)
        
        # 加载按钮
        load_btn = QPushButton("加载图像")
        load_btn.clicked.connect(self.load_images)
        load_btn.setMinimumHeight(35)
        load_btn.setStyleSheet("QPushButton { font-weight: bold; }")
        
        # 审核模式切换按钮
        self.review_mode_btn = QPushButton("切换到审核模式")
        self.review_mode_btn.setCheckable(True)
        self.review_mode_btn.clicked.connect(self.on_review_mode_toggle)
        self.review_mode_btn.setMinimumHeight(35)
        self._update_review_mode_button_style()
        
        buttons_layout.addWidget(self.group_by_id_checkbox)
        buttons_layout.addWidget(self.show_label_count_checkbox)
        buttons_layout.addStretch()
        buttons_layout.addWidget(load_btn)
        buttons_layout.addWidget(self.review_mode_btn)
        buttons_layout.addStretch()
        path_layout.addLayout(buttons_layout)
        
        return path_group
    
    def _connect_signals(self):
        """连接信号和槽"""
        # 图像列表组件信号
        self.image_list_widget.image_selected.connect(self.on_image_selected)
        self.image_list_widget.batch_selected.connect(self.on_batch_selected)
        
        # 标注框编辑组件信号
        self.bbox_editor_widget.bbox_selected.connect(self.on_bbox_selected)
        self.bbox_editor_widget.bbox_class_changed.connect(self.on_bbox_class_changed)
        self.bbox_editor_widget.bbox_deleted.connect(self.on_bbox_deleted)
        self.bbox_editor_widget.add_bbox_requested.connect(self.on_add_bbox_requested)
        
        # 船舶分类组件信号
        self.ship_classifier_widget.ship_type_selected.connect(self.on_ship_type_selected)
        self.ship_classifier_widget.discard_single_requested.connect(self.on_discard_single_requested)
        self.ship_classifier_widget.discard_group_requested.connect(self.on_discard_group_requested)
        self.ship_classifier_widget.auto_classify_requested.connect(self.on_auto_classify_requested)
        
        # 图像查看器组件信号
        self.image_viewer_widget.bbox_selected.connect(self.on_viewer_bbox_selected)
        self.image_viewer_widget.bbox_created.connect(self.on_bbox_created)
        self.image_viewer_widget.bbox_modified.connect(self.on_bbox_modified)
        self.image_viewer_widget.show_class_menu_requested.connect(self.on_show_class_menu_requested)
        
        # 添加快捷键
        self._setup_shortcuts()
    
    def _setup_shortcuts(self):
        """设置快捷键"""
        # Q键快捷键，用于触发添加标注框功能
        self.add_bbox_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Q), self)
        self.add_bbox_shortcut.activated.connect(self.on_add_bbox_requested)
        self.add_bbox_shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
        
        # W和S键作为上下键的替代
        self.key_w_shortcut = QShortcut(QKeySequence(Qt.Key.Key_W), self)
        self.key_w_shortcut.activated.connect(self.on_key_w_shortcut_activated)
        self.key_w_shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
        
        self.key_s_shortcut = QShortcut(QKeySequence(Qt.Key.Key_S), self)
        self.key_s_shortcut.activated.connect(self.on_key_s_shortcut_activated)
        self.key_s_shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
        
        # T键快捷键，用于清空当前图像的所有标签
        self.delete_shortcut = QShortcut(QKeySequence(Qt.Key.Key_T), self)
        self.delete_shortcut.activated.connect(self.clear_all_labels)
        self.delete_shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
        
        # U键快捷键，用于批量丢弃当前选中与之前的所有图片（仅在直接加载模式下）
        self.key_u_shortcut = QShortcut(QKeySequence(Qt.Key.Key_U), self)
        self.key_u_shortcut.activated.connect(self.on_key_u_shortcut_activated)
        self.key_u_shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
        
        # 数字键1-9快捷键
        self.number_shortcuts = []
        for i in range(1, 10):
            shortcut = QShortcut(QKeySequence(getattr(Qt.Key, f"Key_{i}")), self)
            shortcut.activated.connect(lambda idx=i-1: self.on_number_shortcut_activated(idx))
            shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
            self.number_shortcuts.append(shortcut)
    
    def _set_default_paths(self):
        """设置默认路径"""
        # 如果下拉框为空且有默认配置，则使用默认路径
        if config.DEFAULT_SOURCE_DIR and self.source_dir_combo.count() == 0:
            self.source_dir = config.DEFAULT_SOURCE_DIR
            self.source_dir_combo.addItem(self.source_dir)
            self.source_dir_combo.setCurrentText(self.source_dir)
            # 保存到历史记录
            self._add_to_history(self.source_dir_combo, self.source_dir, "source_directories")
        elif self.source_dir_combo.count() > 0:
            # 如果有历史记录，使用第一个作为当前选择
            self.source_dir = self.source_dir_combo.itemText(0)
            self.source_dir_combo.setCurrentText(self.source_dir)
        
        if config.DEFAULT_TARGET_DIR and self.target_dir_combo.count() == 0:
            self.target_dir = config.DEFAULT_TARGET_DIR
            self.target_dir_combo.addItem(self.target_dir)
            self.target_dir_combo.setCurrentText(self.target_dir)
            # 保存到历史记录
            self._add_to_history(self.target_dir_combo, self.target_dir, "target_directories")
        elif self.target_dir_combo.count() > 0:
            # 如果有历史记录，使用第一个作为当前选择
            self.target_dir = self.target_dir_combo.itemText(0)
            self.target_dir_combo.setCurrentText(self.target_dir)
            
        # 如果有默认源目录，尝试自动查找子目录
        if self.source_dir:
            images_dir, labels_dir = self.get_images_and_labels_dirs(self.source_dir)
            if images_dir:
                self.images_subdir = images_dir
            if labels_dir:
                self.labels_subdir = labels_dir
        
        # 初始化按钮样式
        self._update_review_mode_button_style()
    
    def get_images_and_labels_dirs(self, source_dir):
        """在源目录下查找图像和标签子文件夹"""
        images_dir = None
        labels_dir = None
        
        # 模式1: 检查"images"和"labels"子文件夹
        potential_images_dir = os.path.join(source_dir, "images")
        potential_labels_dir = os.path.join(source_dir, "labels")
        
        if os.path.isdir(potential_images_dir):
            images_dir = potential_images_dir
        
        if os.path.isdir(potential_labels_dir):
            labels_dir = potential_labels_dir
        
        # 如果模式1成功找到了两个目录，直接返回
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
    
    def browse_source_dir(self):
        """浏览源文件目录"""
        current_dir = self.source_dir_combo.currentText() or os.path.expanduser("~")
        directory = QFileDialog.getExistingDirectory(
            self, "选择源文件目录", current_dir
        )
        if directory:
            self.source_dir = directory
            
            # 添加到历史记录和下拉框
            self._add_to_history(self.source_dir_combo, directory, "source_directories")
            
            # 自动检测images和labels子文件夹
            images_dir, labels_dir = self.get_images_and_labels_dirs(directory)
            
            if images_dir and labels_dir:
                self.images_subdir = images_dir
                self.labels_subdir = labels_dir
                self.status_bar.showMessage(f"已找到图像目录: {os.path.basename(images_dir)} 和标签目录: {os.path.basename(labels_dir)}")
            else:
                self.status_bar.showMessage("在选择的目录中未找到有效的图像和标签子文件夹")
                QMessageBox.warning(
                    self, 
                    "未找到有效目录结构", 
                    "未在选择的目录中找到有效的图像和标签子文件夹。\n\n"
                    "支持的目录结构:\n"
                    "1. [选择的目录]/images 和 [选择的目录]/labels\n"
                    "2. [选择的目录]/original_snaps 和 [选择的目录]/original_snaps_labels\n\n"
                    "请检查目录结构是否符合上述模式。"
                )
    
    def browse_target_dir(self):
        """浏览目标目录"""
        current_dir = self.target_dir_combo.currentText() or os.path.expanduser("~")
        directory = QFileDialog.getExistingDirectory(
            self, "选择目标目录", current_dir
        )
        if directory:
            self.target_dir = directory
            
            # 添加到历史记录和下拉框
            self._add_to_history(self.target_dir_combo, directory, "target_directories")
    
    def load_images(self):
        """加载图像"""
        if not self.source_dir or not os.path.exists(self.source_dir):
            QMessageBox.critical(self, "错误", "请选择有效的源文件目录")
            return
        
        if not self.images_subdir or not os.path.exists(self.images_subdir):
            QMessageBox.critical(self, "错误", "在源目录中未找到images子文件夹")
            return
                
        if not self.labels_subdir or not os.path.exists(self.labels_subdir):
            QMessageBox.critical(self, "错误", "在源目录中未找到labels子文件夹")
            return
        
        # 使用图像列表组件加载图像，传递标签目录参数
        self.image_list_widget.load_images(self.images_subdir, self.labels_subdir)
        self.image_files = self.image_list_widget.image_files
        
        # 更新组件状态
        self.image_list_widget.set_group_by_id(self.group_by_id)
        self.image_list_widget.set_show_label_count(self.show_label_count_checkbox.isChecked())
        self.ship_classifier_widget.set_group_by_id(self.group_by_id)
        
        # 更新状态栏
        mode_text = "【审核模式】" if self.is_review_mode else "【标注模式】"
        group_text = "按ID分组" if self.group_by_id else "直接加载"
        action_text = "删除源文件" if self.is_review_mode else "保留源文件"
        self.status_bar.showMessage(f"{mode_text} ({group_text}, {action_text}): 已加载 {len(self.image_files)} 个图像")
    
    def on_group_by_id_toggle(self):
        """处理按ID分组勾选框状态变化事件"""
        self.group_by_id = self.group_by_id_checkbox.isChecked()
        
        # 清空批量选择状态（如果有）
        if self.image_list_widget.is_in_batch_mode():
            self.image_list_widget.clear_batch_selection()
            self.ship_classifier_widget.set_batch_mode(False)
        
        # 更新组件状态
        self.image_list_widget.set_group_by_id(self.group_by_id)
        self.ship_classifier_widget.set_group_by_id(self.group_by_id)
        
        mode_text = "按ID分组" if self.group_by_id else "直接加载"
        self.status_bar.showMessage(f"已切换到{mode_text}模式")
    
    def on_show_label_count_toggle(self):
        """处理显示标签数勾选框状态变化事件"""
        show_label_count = self.show_label_count_checkbox.isChecked()
        
        # 更新图像列表组件的显示标签数设置
        self.image_list_widget.set_show_label_count(show_label_count)
        
        # 如果当前已经加载了图像，重新更新显示
        if self.image_files:
            self.image_list_widget._update_tree_view()
        
        count_text = "显示标签数" if show_label_count else "隐藏标签数"
        self.status_bar.showMessage(f"已切换到{count_text}模式")
    
    def _update_review_mode_button_style(self):
        """更新审核模式按钮的样式"""
        if self.is_review_mode:
            # 审核模式：红色背景，表示危险操作
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
            # 标注模式：绿色背景，表示安全操作
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
    
    def on_review_mode_toggle(self):
        """处理模式切换按钮点击事件"""
        self.is_review_mode = not self.is_review_mode
        
        # 更新按钮样式和文本
        self._update_review_mode_button_style()
        
        # 更新组件状态
        self.image_list_widget.set_review_mode(self.is_review_mode)
        self.ship_classifier_widget.set_review_mode(self.is_review_mode)
        
        mode_text = "【审核模式】" if self.is_review_mode else "【标注模式】"
        action_text = "删除源文件" if self.is_review_mode else "保留源文件"
        self.status_bar.showMessage(f"已切换到{mode_text}，操作后将{action_text}")
    
    # 信号处理方法
    def on_image_selected(self, image_path, image_idx):
        """处理图像选择事件"""
        # 检查图像列表组件是否已退出批量模式，如果是，同步更新船舶分类组件
        if not self.image_list_widget.is_in_batch_mode() and self.ship_classifier_widget.batch_mode:
            self.ship_classifier_widget.set_batch_mode(False)
        
        # 保存之前图像的标签修改（如果有）
        self._save_current_labels()
        
        self.current_image_idx = image_idx
        
        # 获取对应的标签文件
        label_path = file_utils.get_corresponding_label_file(image_path, self.labels_subdir)
        
        # 加载图像到查看器
        success = self.image_viewer_widget.load_image(image_path, label_path)
        if success:
            # 更新标注框编辑器
            labels = self.image_viewer_widget.get_current_labels()
            self.bbox_editor_widget.update_bbox_list(labels)
            
            self.status_bar.showMessage(f"当前查看: {os.path.basename(image_path)}")
        else:
            self.status_bar.showMessage(f"无法加载图像: {os.path.basename(image_path)}")
    
    def on_batch_selected(self, selected_paths):
        """处理批量选择事件"""
        if not selected_paths:
            # 退出批量模式
            self.ship_classifier_widget.set_batch_mode(False)
            self.status_bar.showMessage("已退出批量选择模式")
            return
        
        # 进入批量模式
        batch_count = len(selected_paths)
        self.ship_classifier_widget.set_batch_mode(True, batch_count)
        
        # 清空当前图像显示（批量模式下不显示单个图像）
        self.image_viewer_widget.clear_image()
        self.bbox_editor_widget.clear_bbox_list()
        
        self.status_bar.showMessage(f"批量选择模式：已选择 {batch_count} 个图像")
    
    def on_bbox_selected(self, bbox_index):
        """处理标注框选择事件"""
        self.image_viewer_widget.set_selected_bbox(bbox_index)
        self.bbox_editor_widget.set_selected_bbox(bbox_index)
    
    def on_viewer_bbox_selected(self, bbox_index):
        """处理查看器中的标注框选择事件"""
        self.bbox_editor_widget.set_selected_bbox(bbox_index)
    
    def on_bbox_class_changed(self, bbox_index, new_class_id):
        """处理标注框类别改变事件"""
        # 更新标签数据
        if self.image_viewer_widget.current_yolo_label:
            self.image_viewer_widget.current_yolo_label.update_label_class(bbox_index, new_class_id)
            
            # 保存标签到原文件
            self._save_current_labels()
            
            # 更新显示
            self.image_viewer_widget.update_display_image(adjust_view=False)
            labels = self.image_viewer_widget.get_current_labels()
            self.bbox_editor_widget.update_bbox_list(labels)
    
    def on_bbox_deleted(self, bbox_index):
        """处理标注框删除事件"""
        # 删除标签
        if self.image_viewer_widget.current_yolo_label:
            self.image_viewer_widget.current_yolo_label.remove_label(bbox_index)
            
            # 保存标签到原文件
            self._save_current_labels()
            
            # 更新显示
            self.image_viewer_widget.update_display_image(adjust_view=False)
            labels = self.image_viewer_widget.get_current_labels()
            self.bbox_editor_widget.update_bbox_list(labels)
    
    def on_add_bbox_requested(self):
        """处理添加标注框请求"""
        if not self.image_viewer_widget.current_image:
            QMessageBox.warning(self, "警告", "请先选择一个图像")
            return
        
        # 开始绘制标注框
        self.image_viewer_widget.start_drawing_bbox()
        self.status_bar.showMessage("【绘制模式】请在图像上点击并拖动鼠标创建新标注框")
    
    def on_bbox_created(self, class_id, center_x, center_y, width, height):
        """处理标注框创建事件"""
        # 添加新标签
        if self.image_viewer_widget.current_yolo_label:
            self.image_viewer_widget.current_yolo_label.add_label(class_id, center_x, center_y, width, height)
            
            # 保存标签到原文件
            self._save_current_labels()
            
            # 更新显示
            self.image_viewer_widget.update_display_image(adjust_view=False)
            labels = self.image_viewer_widget.get_current_labels()
            self.bbox_editor_widget.update_bbox_list(labels)
    
    def on_bbox_modified(self, bbox_index, center_x, center_y, width, height):
        """处理标注框修改事件"""
        # 更新标签坐标
        if self.image_viewer_widget.current_yolo_label:
            self.image_viewer_widget.current_yolo_label.update_label_coords(
                bbox_index, center_x, center_y, width, height
            )
            
            # 保存标签到原文件
            self._save_current_labels()
            
            # 更新显示
            self.image_viewer_widget.update_display_image(adjust_view=False)
    
    def on_show_class_menu_requested(self, bbox_index, position):
        """处理显示类别菜单请求"""
        global_pos = self.image_viewer_widget.graphics_view.viewport().mapToGlobal(position)
        self.bbox_editor_widget.show_class_menu_for_bbox(bbox_index, global_pos)
    
    def on_ship_type_selected(self, class_id, class_name):
        """处理船舶类型选择事件"""
        # 检查是否为批量模式
        if self.image_list_widget.is_in_batch_mode():
            self._process_batch_labeling(class_id, class_name)
        else:
            # 实现标注和移动逻辑
            self._process_labeling(class_id, class_name)
    
    def _process_labeling(self, class_id, class_name):
        """统一的标注处理函数
        
        Args:
            class_id: 船舶类型ID
            class_name: 船舶类型名称
        """
        if not self.image_list_widget.group_by_id:
            # 简单模式：只处理当前图像
            if not self.image_viewer_widget.current_image or not self.image_viewer_widget.current_yolo_label:
                QMessageBox.warning(self, "警告", "请先选择一个图像")
                return
            
            # 获取当前图像信息
            current_img_path = self.image_viewer_widget.current_yolo_label.image_path
            current_img_name = os.path.basename(current_img_path)
            
            # 先保存任何已有的修改
            if self.image_viewer_widget.current_yolo_label.is_modified():
                self.image_viewer_widget.current_yolo_label.save_labels()
            
            # 更新所有标签的类别
            labels = self.image_viewer_widget.current_yolo_label.get_labels()
            if not labels:
                QMessageBox.warning(self, "警告", f"图像 {current_img_name} 没有标签数据")
                return
            
            for i in range(len(labels)):
                self.image_viewer_widget.current_yolo_label.update_label_class(i, class_id)
            
            # 移动文件到目标目录
            success, error_msg = self.image_viewer_widget.current_yolo_label.move_to_target(self.target_dir, class_id)
            
            if success:
                # 记录标注操作（单张图片）
                self._record_annotation(1)
                
                # 在审核模式下删除源文件
                if self.is_review_mode:
                    try:
                        if os.path.exists(current_img_path):
                            os.remove(current_img_path)
                        
                        label_file = file_utils.get_corresponding_label_file(current_img_path, self.labels_subdir)
                        if label_file and os.path.exists(label_file):
                            os.remove(label_file)
                    except Exception as e:
                        QMessageBox.warning(self, "警告", f"删除源文件时发生错误: {e}")
                
                # 清空当前显示（在移除之前）
                self.clear_current_display()
                
                # 从图像列表中移除当前图像（会自动选择下一张）
                self.image_list_widget.remove_current_image()
                
                self.status_bar.showMessage(f"已将图像 {current_img_name} 标注为 {class_name} 并移动到目标目录")
            else:
                QMessageBox.critical(self, "错误", f"移动文件失败: {error_msg}")
            
            return
        
        # 分组模式：处理整个组
        current_group_id = self.image_list_widget.current_group_id
        if not current_group_id:
            QMessageBox.warning(self, "警告", "请先选择一个图像组")
            return
        
        # 处理整个组的图像
        if current_group_id in self.image_list_widget.image_groups_by_id:
            img_files = self.image_list_widget.image_groups_by_id[current_group_id]
            success_count = 0
            error_msgs = []
            
            for img_file in img_files:
                # 如果是当前图像，使用已加载的当前标签对象（可能包含修改）
                if (self.image_viewer_widget.current_image and 
                    self.image_viewer_widget.current_yolo_label and 
                    img_file == self.image_viewer_widget.current_yolo_label.image_path):
                    
                    yolo_label = self.image_viewer_widget.current_yolo_label
                    
                    # 先保存任何已有的修改
                    if yolo_label.is_modified():
                        yolo_label.save_labels()
                    
                    # 更新所有标签的类别
                    for i in range(len(yolo_label.get_labels())):
                        yolo_label.update_label_class(i, class_id)
                    
                    # 移动文件到目标目录
                    success, error_msg = yolo_label.move_to_target(self.target_dir, class_id)
                    if success:
                        success_count += 1
                    else:
                        error_msgs.append(f"移动文件 {os.path.basename(img_file)} 失败: {error_msg}")
                else:
                    # 对于其他图像，按原有方式处理
                    # 获取对应的标签文件
                    label_file = file_utils.get_corresponding_label_file(img_file, self.labels_subdir)
                    if not label_file:
                        error_msgs.append(f"找不到图像 {os.path.basename(img_file)} 的标签文件")
                        continue
                    
                    # 加载标签并更新所有标签的类别
                    yolo_label = YoloLabel(img_file, label_file)
                    labels = yolo_label.get_labels()
                    
                    if not labels:
                        error_msgs.append(f"图像 {os.path.basename(img_file)} 没有标签数据")
                        continue
                    
                    # 更新所有标签的类别
                    for i in range(len(labels)):
                        yolo_label.update_label_class(i, class_id)
                    
                    # 移动文件到目标目录
                    success, error_msg = yolo_label.move_to_target(self.target_dir, class_id)
                    if success:
                        success_count += 1
                    else:
                        error_msgs.append(f"移动文件 {os.path.basename(img_file)} 失败: {error_msg}")
            
            # 记录标注操作（整个组）
            if success_count > 0:
                self._record_annotation(success_count)
            
            # 根据模式决定是否删除原始文件
            if self.is_review_mode:
                for img_file in img_files:
                    try:
                        # 删除图像和标签文件
                        if os.path.exists(img_file):
                            os.remove(img_file)
                        
                        label_file = file_utils.get_corresponding_label_file(img_file, self.labels_subdir)
                        if label_file and os.path.exists(label_file):
                            os.remove(label_file)
                    except Exception as e:
                        error_msgs.append(f"删除文件 {os.path.basename(img_file)} 失败: {e}")
            
            # 显示处理结果
            if error_msgs:
                error_text = "\n".join(error_msgs)
                QMessageBox.warning(self, "部分文件处理失败", 
                                  f"成功处理 {success_count} 个文件，失败的文件:\n{error_text}")
            else:
                action_text = "移动并删除源文件" if self.is_review_mode else "移动"
                self.status_bar.showMessage(f"成功将组 {current_group_id} 的 {success_count} 个文件标注为 {class_name} 并{action_text}")
            
            # 清空当前显示（在移除之前）
            self.clear_current_display()
            
            # 从图像列表中移除整个组（会自动选择下一个组）
            self.image_list_widget.remove_current_group()
    
    def _record_annotation(self, count=1):
        """记录标注操作
        
        Args:
            count: 标注的图片数量
        """
        current_time = time.time()
        
        # 记录标注时间，为了更准确的速度计算，给每张图片分配略微不同的时间戳
        for i in range(count):
            # 为批量操作中的每张图片分配微小的时间差（毫秒级）
            timestamp = current_time + (i * 0.001)  # 每张图片间隔1毫秒
            self.annotation_times.append(timestamp)
            self.total_annotations += 1
    
    def _update_speed_display(self):
        """更新标注速度显示"""
        current_time = time.time()
        
        # 计算实时速度（最近1分钟内的标注）
        realtime_speed = 0.0
        recent_annotations = [t for t in self.annotation_times if current_time - t <= 60.0]
        if len(recent_annotations) >= 2:
            time_span = current_time - recent_annotations[0]
            if time_span > 0:
                realtime_speed = len(recent_annotations) / time_span
        
        # 使用实时速度作为显示速度
        display_speed = realtime_speed
        
        # 根据速度选择不同的图标和颜色
        if display_speed >= 2.0:
            icon = "🚀"
            color = "#FF6B35"  # 橙红色 - 超快
            bg_color = "rgba(255, 107, 53, 0.15)"
        elif display_speed >= 1.0:
            icon = "⚡"
            color = "#2E8B57"  # 海绿色 - 快速
            bg_color = "rgba(46, 139, 87, 0.15)"
        elif display_speed >= 0.5:
            icon = "🎯"
            color = "#4169E1"  # 皇家蓝 - 中等
            bg_color = "rgba(65, 105, 225, 0.15)"
        elif display_speed > 0:
            icon = "🐌"
            color = "#8B4513"  # 马鞍棕 - 慢速
            bg_color = "rgba(139, 69, 19, 0.15)"
        else:
            icon = "💤"
            color = "#696969"  # 暗灰色 - 无活动
            bg_color = "rgba(105, 105, 105, 0.15)"
        
        # 更新显示文本和样式
        speed_text = f"{icon} 标注速度: {display_speed:.1f} 图片/秒"
        if self.total_annotations > 0:
            speed_text += f" (总计: {self.total_annotations})"
        
        self.speed_label.setText(speed_text)
        self.speed_label.setStyleSheet(f"""
            QLabel {{
                color: {color};
                font-weight: bold;
                padding: 2px 8px;
                border: 1px solid {color};
                border-radius: 3px;
                background-color: {bg_color};
            }}
        """)
    
    def clear_current_display(self):
        """清空当前显示"""
        self.image_viewer_widget.clear_image()
        self.bbox_editor_widget.clear_bbox_list()
    
    def on_discard_single_requested(self):
        """处理丢弃单个请求"""
        # 检查是否为批量模式
        if self.image_list_widget.is_in_batch_mode():
            self._discard_batch_images()
        else:
            if not self.image_viewer_widget.current_image:
                QMessageBox.warning(self, "警告", "请先选择一个图像")
                return
            
            # 根据当前模式删除或保留原文件
            self._discard_single_image(delete_files=self.is_review_mode)
    
    def _discard_single_image(self, delete_files=False):
        """丢弃单个图像
        
        Args:
            delete_files: 是否删除原始文件
        """
        if not self.image_viewer_widget.current_image or not self.image_viewer_widget.current_yolo_label:
            QMessageBox.warning(self, "警告", "没有可丢弃的图像")
            return
        
        current_img_path = self.image_viewer_widget.current_yolo_label.image_path
        current_img_name = os.path.basename(current_img_path)
        
        # 根据模式处理文件
        if delete_files:
            try:
                # 删除图像和标签文件
                if os.path.exists(current_img_path):
                    os.remove(current_img_path)
                
                label_path = file_utils.get_corresponding_label_file(current_img_path, self.labels_subdir)
                if label_path and os.path.exists(label_path):
                    os.remove(label_path)
            except Exception as e:
                QMessageBox.critical(self, "错误", f"删除文件时发生错误: {e}")
                return
        
        # 记录丢弃操作（单张图片）
        self._record_annotation(1)
        
        # 清空当前显示（在移除之前）
        self.clear_current_display()
        
        # 从图像列表中移除当前图像（会自动选择下一张）
        self.image_list_widget.remove_current_image()
        
        # 更新状态栏
        action_text = "删除" if delete_files else "从列表移除"
        self.status_bar.showMessage(f"已{action_text}图像: {current_img_name}")
    
    def on_discard_group_requested(self):
        """处理丢弃整组请求"""
        # 检查是否为批量模式
        if self.image_list_widget.is_in_batch_mode():
            # 在非分组模式的批量选择中，两个丢弃按钮功能相同
            self._discard_batch_images()
        else:
            if not self.image_list_widget.group_by_id:
                QMessageBox.warning(self, "警告", "当前不是分组模式")
                return
                
            if not self.image_list_widget.current_group_id:
                QMessageBox.warning(self, "警告", "请先选择一个图像组")
                return
            
            # 根据当前模式删除或保留原文件
            self._discard_group(delete_files=self.is_review_mode)
    
    def _discard_group(self, delete_files=False):
        """丢弃整个ID组
        
        Args:
            delete_files: 是否删除原始文件
        """
        current_group_id = self.image_list_widget.current_group_id
        if not current_group_id or current_group_id not in self.image_list_widget.image_groups_by_id:
            QMessageBox.warning(self, "警告", "没有可丢弃的图像组")
            return
        
        img_files = self.image_list_widget.image_groups_by_id[current_group_id]
        success_count = 0
        error_msgs = []
        
        if delete_files:
            # 删除模式：删除原始文件
            for img_file in img_files:
                try:
                    # 删除图像和标签文件
                    if os.path.exists(img_file):
                        os.remove(img_file)
                        success_count += 1
                    
                    label_file = file_utils.get_corresponding_label_file(img_file, self.labels_subdir)
                    if label_file and os.path.exists(label_file):
                        os.remove(label_file)
                except Exception as e:
                    error_msgs.append(f"删除文件 {os.path.basename(img_file)} 失败: {e}")
        else:
            # 仅从列表中移除，不删除原文件
            success_count = len(img_files)
        
        # 记录丢弃操作（整个组）
        if success_count > 0:
            self._record_annotation(success_count)
        
        # 清空当前显示（在移除之前）
        self.clear_current_display()
        
        # 从图像列表中移除整个组（会自动选择下一个组）
        self.image_list_widget.remove_current_group()
        
        # 显示处理结果
        if error_msgs:
            error_text = "\n".join(error_msgs)
            QMessageBox.warning(self, "部分文件处理失败", 
                              f"成功处理 {success_count} 个文件，失败的文件:\n{error_text}")
        
        # 更新状态栏信息
        action_text = "删除" if delete_files else "从列表移除"
        self.status_bar.showMessage(f"已{action_text} ID '{current_group_id}' 的 {success_count} 个文件")
    
    def on_auto_classify_requested(self):
        """处理自动分类请求"""
        # 检查是否为批量模式
        if self.image_list_widget.is_in_batch_mode():
            self._auto_classify_batch_images()
        else:
            if not self.image_viewer_widget.current_image:
                QMessageBox.warning(self, "警告", "请先选择一个图像")
                return
            
            # 执行自动分类
            self._auto_classify_single_image()
    
    def _auto_classify_batch_images(self):
        """批量自动分类图像"""
        selected_paths = self.image_list_widget.get_batch_selected_items()
        if not selected_paths:
            QMessageBox.warning(self, "警告", "没有选择的图像")
            return
        
        # 记录第一个选中项的索引，作为操作后的起始位置
        first_selected_path = selected_paths[0]
        start_idx = self.image_list_widget.image_files.index(first_selected_path) if first_selected_path in self.image_list_widget.image_files else 0
        
        success_count = 0
        error_msgs = []
        mixed_count = 0
        background_count = 0
        
        for img_file in selected_paths:
            # 获取对应的标签文件
            label_file = file_utils.get_corresponding_label_file(img_file, self.labels_subdir)
            if not label_file:
                error_msgs.append(f"找不到图像 {os.path.basename(img_file)} 的标签文件")
                continue
            
            # 加载标签并分析类别
            yolo_label = YoloLabel(img_file, label_file)
            labels = yolo_label.get_labels()
            
            if not labels:
                # 没有标签数据，移动到背景分类
                move_success, error_msg = self._move_file_to_category(yolo_label, "背景")
                if move_success:
                    background_count += 1
                    success_count += 1
                else:
                    error_msgs.append(f"移动图像 {os.path.basename(img_file)} 到背景类别失败: {error_msg}")
                continue
            
            # 获取所有不同的类别
            unique_class_ids = set()
            for label in labels:
                if len(label) == 5:
                    class_id = int(label[0])
                    unique_class_ids.add(class_id)
            
            if not unique_class_ids:
                # 存在标签但标签不合法，只警告不移动
                error_msgs.append(f"图像 {os.path.basename(img_file)} 存在标签但格式不合法，已跳过")
                continue
            
            # 根据类别数量决定移动方式
            if len(unique_class_ids) > 1:
                # 多个类别，移动到混合分类
                move_success, error_msg = self._move_file_to_category(yolo_label, "混合")
                if move_success:
                    mixed_count += 1
                    success_count += 1
                else:
                    error_msgs.append(f"移动图像 {os.path.basename(img_file)} 到混合类别失败: {error_msg}")
            else:
                # 单一类别，移动到对应分类
                class_id = list(unique_class_ids)[0]
                move_success, error_msg = yolo_label.move_to_target(self.target_dir, class_id)
                if move_success:
                    success_count += 1
                else:
                    error_msgs.append(f"移动图像 {os.path.basename(img_file)} 失败: {error_msg}")
        
        # 记录自动分类操作
        if success_count > 0:
            self._record_annotation(success_count)
        
        # 根据模式决定是否删除原始文件
        if self.is_review_mode:
            for img_file in selected_paths:
                try:
                    # 删除图像和标签文件
                    if os.path.exists(img_file):
                        os.remove(img_file)
                    
                    label_file = file_utils.get_corresponding_label_file(img_file, self.labels_subdir)
                    if label_file and os.path.exists(label_file):
                        os.remove(label_file)
                except Exception as e:
                    error_msgs.append(f"删除文件 {os.path.basename(img_file)} 失败: {e}")
        
        # 从图像列表中移除批量选择的图像
        self.image_list_widget.remove_batch_selected_images()
        
        # 退出批量模式
        self.ship_classifier_widget.set_batch_mode(False)
        
        # 选择指定索引的图像
        self._select_image_at_index(start_idx)
        
        # 显示处理结果
        if error_msgs:
            error_text = "\n".join(error_msgs)
            QMessageBox.warning(self, "部分文件处理失败", 
                              f"成功处理 {success_count} 个文件（其中 {mixed_count} 个移动到混合类别，{background_count} 个移动到背景类别），失败的文件:\n{error_text}")
        else:
            action_text = "移动并删除源文件" if self.is_review_mode else "移动"
            self.status_bar.showMessage(f"成功{action_text} {success_count} 个文件（其中 {mixed_count} 个移动到混合类别，{background_count} 个移动到背景类别）")
    
    def _move_file_to_category(self, yolo_label, category_name):
        """将图像文件移动到指定类别目录
        
        Args:
            yolo_label: YoloLabel对象
            category_name: 类别名称（如"背景"、"混合"）
            
        Returns:
            (bool, str): (是否成功, 错误信息)
        """
        # 保存当前图像信息
        image_path = yolo_label.image_path
        label_path = yolo_label.label_path
        
        # 保存当前修改
        if yolo_label.is_modified():
            yolo_label.save_labels()
        
        try:
            import shutil
            
            # 创建类别目录
            target_dir = os.path.join(self.target_dir, category_name)
            target_img_dir = os.path.join(target_dir, "images")
            target_label_dir = os.path.join(target_dir, "labels")
            os.makedirs(target_img_dir, exist_ok=True)
            os.makedirs(target_label_dir, exist_ok=True)
            
            # 获取文件基本信息
            image_basename = os.path.basename(image_path)
            base_name = os.path.splitext(image_basename)[0]
            
            # 确定目标文件路径
            target_img_path = os.path.join(target_img_dir, image_basename)
            target_label_path = os.path.join(target_label_dir, f"{base_name}{config.LABEL_FILE_EXT}")
            
            # 复制文件
            shutil.copy2(image_path, target_img_path)
            shutil.copy2(label_path, target_label_path)
            
            # 验证文件是否已成功复制
            if not os.path.exists(target_img_path) or not os.path.exists(target_label_path):
                return False, "复制文件到目标目录失败"
            
            return True, ""
        except Exception as e:
            return False, str(e)
    
    def _auto_classify_single_image(self):
        """根据图像中标签类型自动分类当前图像"""
        # 检查是否有当前图像和标签
        if not self.image_viewer_widget.current_image or not self.image_viewer_widget.current_yolo_label:
            QMessageBox.warning(self, "警告", "没有可分类的图像")
            return
        
        # 获取当前图像路径和文件名
        current_img_path = self.image_viewer_widget.current_yolo_label.image_path
        current_img_name = os.path.basename(current_img_path)
        
        # 检查标签数据
        labels = self.image_viewer_widget.current_yolo_label.get_labels()
        if not labels:
            # 没有标签数据，移动到背景分类
            move_success, error_msg = self._move_file_to_category(self.image_viewer_widget.current_yolo_label, "背景")
            
            # 处理移动结果
            if move_success:
                # 记录自动分类操作（单张图片）
                self._record_annotation(1)
                
                # 在审核模式下，删除源文件
                if self.is_review_mode:
                    try:
                        # 删除图像和标签文件
                        if os.path.exists(current_img_path):
                            os.remove(current_img_path)
                        
                        label_path = file_utils.get_corresponding_label_file(current_img_path, self.labels_subdir)
                        if label_path and os.path.exists(label_path):
                            os.remove(label_path)
                    except Exception as e:
                        QMessageBox.warning(self, "警告", f"删除源文件时发生错误: {e}")
                
                # 清空当前显示（在移除之前）
                self.clear_current_display()
                
                # 从图像列表中移除当前图像（会自动选择下一张）
                self.image_list_widget.remove_current_image()
                
                # 更新状态栏
                action_text = "移动并删除源文件" if self.is_review_mode else "移动"
                self.status_bar.showMessage(f"已将图像 {current_img_name} {action_text}到背景类别")
            else:
                QMessageBox.critical(self, "错误", f"移动文件时发生错误: {error_msg}")
            return
        
        # 获取所有不同的类别
        unique_class_ids = set()
        for label in labels:
            if len(label) == 5:
                class_id = int(label[0])
                unique_class_ids.add(class_id)
        
        if not unique_class_ids:
            # 存在标签但标签不合法，只警告不移动
            QMessageBox.warning(self, "警告", f"图像 {current_img_name} 存在标签但格式不合法，无法自动分类")
            return
        
        # 如果有多个不同的类别，则移动到"混合"分类
        if len(unique_class_ids) > 1:
            move_success, error_msg = self._move_file_to_category(self.image_viewer_widget.current_yolo_label, "混合")
        else:
            # 使用唯一的类别ID移动
            class_id = list(unique_class_ids)[0]
            
            # 保存当前修改的标签
            if self.image_viewer_widget.current_yolo_label.is_modified():
                self.image_viewer_widget.current_yolo_label.save_labels()
            
            # 移动文件到目标目录
            move_success, error_msg = self.image_viewer_widget.current_yolo_label.move_to_target(self.target_dir, class_id)
        
        # 处理移动结果
        if move_success:
            # 记录自动分类操作（单张图片）
            self._record_annotation(1)
            
            # 在审核模式下，删除源文件
            if self.is_review_mode:
                try:
                    # 删除图像和标签文件
                    if os.path.exists(current_img_path):
                        os.remove(current_img_path)
                    
                    label_path = file_utils.get_corresponding_label_file(current_img_path, self.labels_subdir)
                    if label_path and os.path.exists(label_path):
                        os.remove(label_path)
                except Exception as e:
                    QMessageBox.warning(self, "警告", f"删除源文件时发生错误: {e}")
            
            # 清空当前显示（在移除之前）
            self.clear_current_display()
            
            # 从图像列表中移除当前图像（会自动选择下一张）
            self.image_list_widget.remove_current_image()
            
            # 更新状态栏
            action_text = "移动并删除源文件" if self.is_review_mode else "移动"
            if len(unique_class_ids) > 1:
                self.status_bar.showMessage(f"已将图像 {current_img_name} {action_text}到混合类别")
            else:
                class_name = self.ship_types.get(str(list(unique_class_ids)[0]), f"未知类型({list(unique_class_ids)[0]})")
                self.status_bar.showMessage(f"已将图像 {current_img_name} {action_text}到 {class_name} 类别")
        else:
            QMessageBox.critical(self, "错误", f"移动文件时发生错误: {error_msg}")
    
    def on_key_w_shortcut_activated(self):
        """处理W键事件，模拟上键行为"""
        # 委托给图像列表组件处理
        self.image_list_widget.navigate_up()
    
    def on_key_s_shortcut_activated(self):
        """处理S键事件，模拟下键行为"""
        # 委托给图像列表组件处理
        self.image_list_widget.navigate_down()
    
    def on_key_u_shortcut_activated(self):
        """处理U键事件，批量丢弃当前选中与之前的所有图片（仅在直接加载模式下）"""
        # 只在直接加载模式下工作
        if self.group_by_id:
            QMessageBox.warning(self, "操作限制", "U键批量丢弃功能仅在直接加载模式下可用")
            return
        
        # 获取当前选中项及之前的所有图片
        images_to_discard = self.image_list_widget.get_current_and_previous_images()
        
        if not images_to_discard:
            QMessageBox.warning(self, "警告", "没有可丢弃的图像")
            return
        
        # 直接执行批量丢弃操作
        self._discard_images_by_paths(images_to_discard)
    
    def on_number_shortcut_activated(self, bbox_index):
        """处理数字键快捷键"""
        # 验证当前是否有图像和标注框数据
        if not self.image_viewer_widget.current_image or not self.image_viewer_widget.current_yolo_label:
            return
            
        # 获取标签数据
        labels = self.image_viewer_widget.get_current_labels()
        if not labels or bbox_index >= len(labels):
            # 索引超出范围或没有标注框
            return
        
        # 设置当前选中的边界框索引
        self.image_viewer_widget.set_selected_bbox(bbox_index)
        self.bbox_editor_widget.set_selected_bbox(bbox_index)
            
        # 获取鼠标在graphics_view中的当前位置
        cursor_pos = self.image_viewer_widget.graphics_view.mapFromGlobal(QCursor.pos())
        
        # 如果鼠标不在视图内，使用视图中心点
        if not self.image_viewer_widget.graphics_view.rect().contains(cursor_pos):
            cursor_pos = QPoint(self.image_viewer_widget.graphics_view.width() // 2, 
                               self.image_viewer_widget.graphics_view.height() // 2)
        
        # 弹出类别选择菜单
        global_pos = self.image_viewer_widget.graphics_view.viewport().mapToGlobal(cursor_pos)
        self.bbox_editor_widget.show_class_menu_for_bbox(bbox_index, global_pos)
    
    def clear_all_labels(self):
        """清空当前图像的所有标签"""
        if self.image_viewer_widget.current_yolo_label:
            self.image_viewer_widget.current_yolo_label.labels = []
            self.image_viewer_widget.current_yolo_label.modified = True
            
            # 保存标签到原文件
            self._save_current_labels()
            
            # 更新显示
            self.image_viewer_widget.update_display_image(adjust_view=False)
            self.bbox_editor_widget.update_bbox_list([])
            
            self.status_bar.showMessage("已清空当前图像的所有标签")
    
    def _save_current_labels(self):
        """保存当前标签到原始文件
        
        Returns:
            是否成功保存
        """
        # 检查是否有当前标签对象且已修改
        if (self.image_viewer_widget.current_yolo_label and 
            self.image_viewer_widget.current_yolo_label.is_modified()):
            
            success = self.image_viewer_widget.current_yolo_label.save_labels()
            if success:
                print(f"已保存标签到 {self.image_viewer_widget.current_yolo_label.label_path}")
                
                # 立即更新左侧列表的标签数显示
                self._update_image_list_display()
                
                return True
            else:
                print(f"保存标签失败: {self.image_viewer_widget.current_yolo_label.label_path}")
                return False
        return False
    
    def _update_image_list_display(self):
        """更新图像列表显示（刷新标签数）"""
        # 获取当前选中的图像路径
        current_image_path = None
        if self.image_viewer_widget.current_yolo_label:
            current_image_path = self.image_viewer_widget.current_yolo_label.image_path
        
        if not current_image_path:
            return
        
        # 直接更新特定图像项的文本显示
        self.image_list_widget.update_image_item_text(current_image_path)
    
    def _process_batch_labeling(self, class_id, class_name):
        """批量标注处理函数
        
        Args:
            class_id: 船舶类型ID
            class_name: 船舶类型名称
        """
        selected_paths = self.image_list_widget.get_batch_selected_items()
        if not selected_paths:
            QMessageBox.warning(self, "警告", "没有选择的图像")
            return
        
        # 记录第一个选中项的索引，作为操作后的起始位置
        first_selected_path = selected_paths[0]
        start_idx = self.image_list_widget.image_files.index(first_selected_path) if first_selected_path in self.image_list_widget.image_files else 0
        
        success_count = 0
        error_msgs = []
        
        for img_file in selected_paths:
            # 获取对应的标签文件
            label_file = file_utils.get_corresponding_label_file(img_file, self.labels_subdir)
            if not label_file:
                error_msgs.append(f"找不到图像 {os.path.basename(img_file)} 的标签文件")
                continue
            
            # 加载标签并更新所有标签的类别
            yolo_label = YoloLabel(img_file, label_file)
            labels = yolo_label.get_labels()
            
            if not labels:
                error_msgs.append(f"图像 {os.path.basename(img_file)} 没有标签数据")
                continue
            
            # 更新所有标签的类别
            for i in range(len(labels)):
                yolo_label.update_label_class(i, class_id)
            
            # 移动文件到目标目录
            success, error_msg = yolo_label.move_to_target(self.target_dir, class_id)
            if success:
                success_count += 1
            else:
                error_msgs.append(f"移动文件 {os.path.basename(img_file)} 失败: {error_msg}")
        
        # 记录批量标注操作
        if success_count > 0:
            self._record_annotation(success_count)
        
        # 根据模式决定是否删除原始文件
        if self.is_review_mode:
            for img_file in selected_paths:
                try:
                    # 删除图像和标签文件
                    if os.path.exists(img_file):
                        os.remove(img_file)
                    
                    label_file = file_utils.get_corresponding_label_file(img_file, self.labels_subdir)
                    if label_file and os.path.exists(label_file):
                        os.remove(label_file)
                except Exception as e:
                    error_msgs.append(f"删除文件 {os.path.basename(img_file)} 失败: {e}")
        
        # 显示处理结果
        if error_msgs:
            error_text = "\n".join(error_msgs)
            QMessageBox.warning(self, "部分文件处理失败", 
                              f"成功处理 {success_count} 个文件，失败的文件:\n{error_text}")
        else:
            action_text = "移动并删除源文件" if self.is_review_mode else "移动"
            self.status_bar.showMessage(f"成功将 {success_count} 个文件标注为 {class_name} 并{action_text}")
        
        # 从图像列表中移除批量选择的图像
        self.image_list_widget.remove_batch_selected_images()
        
        # 退出批量模式
        self.ship_classifier_widget.set_batch_mode(False)
        
        # 选择指定索引的图像
        self._select_image_at_index(start_idx)
    
    def _discard_batch_images(self):
        """丢弃批量选择的图像"""
        selected_paths = self.image_list_widget.get_batch_selected_items()
        if not selected_paths:
            QMessageBox.warning(self, "警告", "没有选择的图像")
            return
        
        # 记录第一个选中项的索引，作为操作后的起始位置
        first_selected_path = selected_paths[0]
        start_idx = self.image_list_widget.image_files.index(first_selected_path) if first_selected_path in self.image_list_widget.image_files else 0
        
        success_count = 0
        error_msgs = []
        
        # 根据模式处理文件
        if self.is_review_mode:
            for img_file in selected_paths:
                try:
                    # 删除图像和标签文件
                    if os.path.exists(img_file):
                        os.remove(img_file)
                        success_count += 1
                    
                    label_file = file_utils.get_corresponding_label_file(img_file, self.labels_subdir)
                    if label_file and os.path.exists(label_file):
                        os.remove(label_file)
                except Exception as e:
                    error_msgs.append(f"删除文件 {os.path.basename(img_file)} 失败: {e}")
        else:
            # 仅从列表中移除，不删除原文件
            success_count = len(selected_paths)
        
        # 记录批量丢弃操作
        if success_count > 0:
            self._record_annotation(success_count)
        
        # 从图像列表中移除批量选择的图像
        self.image_list_widget.remove_batch_selected_images()
        
        # 退出批量模式
        self.ship_classifier_widget.set_batch_mode(False)
        
        # 选择指定索引的图像
        self._select_image_at_index(start_idx)
        
        # 显示处理结果
        if error_msgs:
            error_text = "\n".join(error_msgs)
            QMessageBox.warning(self, "部分文件处理失败", 
                              f"成功处理 {success_count} 个文件，失败的文件:\n{error_text}")
        
        # 更新状态栏信息
        action_text = "删除" if self.is_review_mode else "从列表移除"
        self.status_bar.showMessage(f"已{action_text} {success_count} 个图像")
    
    def _select_image_at_index(self, target_idx=None):
        """选择指定索引的图像"""
        if self.image_list_widget.image_files:
            # 如果没有指定索引，则选择第一张
            if target_idx is None:
                final_idx = 0
            else:
                # 确保索引不超出范围
                final_idx = min(target_idx, len(self.image_list_widget.image_files) - 1)
            
            # 设置新的当前索引
            self.image_list_widget.current_image_idx = final_idx
            target_img_path = self.image_list_widget.image_files[final_idx]
            
            if self.image_list_widget.select_tree_item_by_path(target_img_path):
                self.on_image_selected(target_img_path, final_idx)
    
    def _discard_images_by_paths(self, image_paths):
        """根据指定的图片路径列表丢弃图像
        
        Args:
            image_paths: 要丢弃的图片路径列表
        """
        if not image_paths:
            return
        
        success_count = 0
        error_msgs = []
        
        # 根据模式处理文件
        if self.is_review_mode:
            for img_file in image_paths:
                try:
                    # 删除图像和标签文件
                    if os.path.exists(img_file):
                        os.remove(img_file)
                        success_count += 1
                    
                    label_file = file_utils.get_corresponding_label_file(img_file, self.labels_subdir)
                    if label_file and os.path.exists(label_file):
                        os.remove(label_file)
                except Exception as e:
                    error_msgs.append(f"删除文件 {os.path.basename(img_file)} 失败: {e}")
        else:
            # 仅从列表中移除，不删除原文件
            success_count = len(image_paths)
        
        # 记录批量丢弃操作
        if success_count > 0:
            self._record_annotation(success_count)
        
        # 从图像列表中移除指定的图像
        for img_path in image_paths:
            if img_path in self.image_list_widget.image_files:
                self.image_list_widget.image_files.remove(img_path)
        
        # 清空当前显示
        self.clear_current_display()
        
        # 重新刷新图像列表显示
        self.image_list_widget._update_tree_view()
        
        # 选择第一张可用的图像
        self._select_image_at_index()
        
        # 显示处理结果
        if error_msgs:
            error_text = "\n".join(error_msgs)
            QMessageBox.warning(self, "部分文件处理失败", 
                              f"成功处理 {success_count} 个文件，失败的文件:\n{error_text}")
        
        # 更新状态栏信息
        action_text = "删除" if self.is_review_mode else "从列表移除"
        self.status_bar.showMessage(f"已{action_text} {success_count} 个图像")
    
    def show_model_settings(self):
        """显示模型设置对话框"""
        dialog = ModelSettingsDialog(self)
        
        # 连接模型改变信号
        dialog.model_changed.connect(self._on_model_changed)
        
        # 显示对话框
        dialog.exec()
    
    def _on_model_changed(self, model_name):
        """处理模型更改事件"""
        # 通知图像查看器重置YOLO模型
        self.image_viewer_widget.reset_yolo_model()
        
        # 显示状态栏消息
        self.status_bar.showMessage(f"已切换到模型: {model_name}")

    def run(self):
        """运行应用程序"""
        self.show() 