"""
图像查看器组件
负责图像显示、缩放、平移和标注框交互
"""
import os

from PySide6.QtCore import Qt, QPointF, QRectF, QPoint, Signal, QTimer
from PySide6.QtGui import QPainter, QColor, QPixmap, QPen, QCursor, QFont
from PySide6.QtWidgets import (
    QGroupBox, QVBoxLayout, QHBoxLayout, QGraphicsScene,
    QGraphicsPixmapItem, QPushButton, QStyle, QMessageBox, QMenu, QLabel
)
from ultralytics import YOLO

import config
from models.yolo_label import YoloLabel
from utils import image_utils
from utils.yolo_model_manager import YoloModelManager
from .custom_graphics_view import CustomGraphicsView


class ImageViewerWidget(QGroupBox):
    """图像查看器组件"""
    
    # 信号定义
    bbox_selected = Signal(int)  # 标注框被选中信号 (索引)
    bbox_created = Signal(int, float, float, float, float)  # 标注框被创建信号 (类别ID, 中心x, 中心y, 宽度, 高度)
    bbox_modified = Signal(int, float, float, float, float)  # 标注框被修改信号 (索引, 中心x, 中心y, 宽度, 高度)
    show_class_menu_requested = Signal(int, QPoint)  # 请求显示类别菜单信号 (标注框索引, 位置)
    
    def __init__(self, parent=None):
        """初始化图像查看器组件"""
        super().__init__("图像预览", parent)
        
        # 初始化状态变量
        self.current_image = None  # 当前图像对象(PIL)
        self.current_pixmap = None  # 当前图像的QPixmap对象
        self.current_pixmap_with_boxes = None  # 带有边界框的当前图像
        self.current_yolo_label = None  # 当前YOLO标签对象
        self.selected_bbox_index = -1  # 当前选中的边界框索引
        self.ship_types = config.get_ship_types()
        
        # YOLO预测相关状态变量
        self.yolo_model = None  # YOLO模型
        self.model_manager = YoloModelManager()  # 模型管理器
        self.current_model_name = None  # 当前模型名称
        self.yolo_predictions = []  # YOLO预测结果
        self.show_predictions = False  # 是否显示预测结果
        self.confidence_threshold = 0.4  # 置信度阈值
        
        # 边界框拖动相关
        self.is_dragging = False
        self.dragging_point_index = -1
        self.dragging_bbox_index = -1
        self.original_cursor_pos = None
        self.is_edge_dragging = False
        self.dragging_edge_index = -1
        
        # 绘制新标注框相关
        self.is_drawing_bbox = False
        self.drawing_start_pos = None
        self.drawing_current_pos = None
        
        # 图像平移相关
        self.is_panning = False
        self.last_pan_position = None
        
        # 创建UI
        self._init_ui()
        
        # 连接信号
        self._connect_signals()
    
    def _init_ui(self):
        """初始化UI"""
        # 使用水平布局
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)
        
        # 创建图形视图的垂直布局容器
        graphics_view_container = QVBoxLayout()
        graphics_view_container.setContentsMargins(0, 0, 0, 0)
        
        # 创建图形视图和场景
        self.graphics_view = CustomGraphicsView()
        self.graphics_scene = QGraphicsScene()
        self.graphics_view.setScene(self.graphics_scene)
        self.graphics_view.setMinimumSize(800, 600)
        
        # 设置大小策略
        size_policy = self.graphics_view.sizePolicy()
        size_policy.setHorizontalPolicy(size_policy.Policy.Expanding)
        size_policy.setVerticalPolicy(size_policy.Policy.Expanding)
        size_policy.setHorizontalStretch(1)
        size_policy.setVerticalStretch(1)
        self.graphics_view.setSizePolicy(size_policy)
        
        # 添加图形视图到容器
        graphics_view_container.addWidget(self.graphics_view)
        
        # 创建悬浮的重置缩放按钮
        self.reset_zoom_button = QPushButton(self.graphics_view)
        icon = self.style().standardIcon(QStyle.StandardPixmap.SP_BrowserReload)
        if not icon.isNull():
            self.reset_zoom_button.setIcon(icon)
        else:
            self.reset_zoom_button.setText("↺")
        
        self.reset_zoom_button.setFixedSize(28, 28)
        self.reset_zoom_button.setToolTip("还原缩放")
        self.reset_zoom_button.setStyleSheet("""
            QPushButton {
                background-color: rgba(255, 255, 255, 180);
                border: 1px solid rgba(0, 0, 0, 100);
                border-radius: 14px;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 220);
            }
            QPushButton:pressed {
                background-color: rgba(200, 200, 200, 220);
            }
        """)
        
        # 创建悬浮的YOLO预测按钮
        self.yolo_predict_button = QPushButton(self.graphics_view)
        self.yolo_predict_button.setText("🔍")
        self.yolo_predict_button.setFixedSize(32, 32)
        self.yolo_predict_button.setToolTip("YOLO预测")
        self.yolo_predict_button.setStyleSheet("""
            QPushButton {
                background-color: rgba(0, 122, 204, 180);
                color: white;
                font-size: 14px;
                font-weight: bold;
                border: 1px solid rgba(0, 122, 204, 150);
                border-radius: 16px;
            }
            QPushButton:hover {
                background-color: rgba(0, 122, 204, 220);
                border-color: rgba(0, 122, 204, 200);
            }
            QPushButton:pressed {
                background-color: rgba(0, 100, 180, 220);
            }
            QPushButton:disabled {
                background-color: rgba(180, 180, 180, 180);
                color: rgba(120, 120, 120, 180);
                border-color: rgba(150, 150, 150, 100);
            }
        """)
        
        # 创建悬浮的接受所有预测按钮
        self.accept_all_predictions_button = QPushButton(self.graphics_view)
        self.accept_all_predictions_button.setText("✓")
        self.accept_all_predictions_button.setFixedSize(28, 28)
        self.accept_all_predictions_button.setToolTip("接受所有预测结果")
        self.accept_all_predictions_button.setStyleSheet("""
            QPushButton {
                background-color: rgba(34, 139, 34, 180);
                color: white;
                font-size: 14px;
                font-weight: bold;
                border: 1px solid rgba(34, 139, 34, 150);
                border-radius: 14px;
            }
            QPushButton:hover {
                background-color: rgba(34, 139, 34, 220);
                border-color: rgba(34, 139, 34, 200);
            }
            QPushButton:pressed {
                background-color: rgba(28, 115, 28, 220);
            }
            QPushButton:disabled {
                background-color: rgba(180, 180, 180, 120);
                color: rgba(120, 120, 120, 120);
                border-color: rgba(150, 150, 150, 80);
            }
        """)
        
        # 创建悬浮的删除所有预测按钮（重置预测按钮）
        self.reset_predictions_button = QPushButton(self.graphics_view)
        self.reset_predictions_button.setText("✕")
        self.reset_predictions_button.setFixedSize(28, 28)
        self.reset_predictions_button.setToolTip("删除所有预测结果")
        self.reset_predictions_button.setStyleSheet("""
            QPushButton {
                background-color: rgba(255, 69, 0, 180);
                color: white;
                font-size: 12px;
                font-weight: bold;
                border: 1px solid rgba(255, 69, 0, 150);
                border-radius: 14px;
            }
            QPushButton:hover {
                background-color: rgba(255, 69, 0, 220);
                border-color: rgba(255, 69, 0, 200);
            }
            QPushButton:pressed {
                background-color: rgba(220, 50, 0, 220);
            }
            QPushButton:disabled {
                background-color: rgba(180, 180, 180, 120);
                color: rgba(120, 120, 120, 120);
                border-color: rgba(150, 150, 150, 80);
            }
        """)
        
        # 默认隐藏预测相关按钮
        self.accept_all_predictions_button.setVisible(False)
        self.reset_predictions_button.setVisible(False)
        
        # 创建YOLO预测结果提示标签
        self.prediction_result_label = QLabel(self.graphics_view)
        self.prediction_result_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.prediction_result_label.setStyleSheet("""
            QLabel {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 rgba(0, 122, 204, 250), stop:1 rgba(0, 100, 180, 250));
                color: white;
                font-family: "Microsoft YaHei", "Segoe UI", Arial, sans-serif;
                font-size: 18px;
                font-weight: bold;
                padding: 16px 28px;
                border-radius: 25px;
                border: 3px solid rgba(255, 255, 255, 220);
                box-shadow: 0px 8px 16px rgba(0, 0, 0, 50);
            }
        """)
        self.prediction_result_label.setVisible(False)
        
        # 创建结果提示定时器
        self.result_timer = QTimer(self)
        self.result_timer.setSingleShot(True)
        self.result_timer.timeout.connect(self._hide_prediction_result)
        
        # 更新YOLO按钮提示文本
        self._update_yolo_button_tooltip()
        
        # 将图形视图容器添加到主布局
        layout.addLayout(graphics_view_container, 1)
    
    def _connect_signals(self):
        """连接信号"""
        # 设置鼠标事件处理
        self.graphics_view.on_mouse_press = self.on_graphics_view_click
        self.graphics_view.on_mouse_move = self.on_graphics_view_move
        self.graphics_view.on_mouse_release = self.on_graphics_view_release
        
        # 连接重置缩放按钮
        self.reset_zoom_button.clicked.connect(self.adjust_image_to_view)
        
        # 连接YOLO预测按钮
        self.yolo_predict_button.clicked.connect(self.perform_yolo_prediction)
        
        # 连接接受所有预测按钮
        self.accept_all_predictions_button.clicked.connect(self.accept_all_predictions)
        
        # 连接删除所有预测按钮
        self.reset_predictions_button.clicked.connect(self.reset_predictions)
    
    def load_yolo_model(self, model_name=None):
        """加载YOLO模型
        
        Args:
            model_name: 指定的模型文件名，如果为None则使用配置中的模型
        """
        
        try:
            # 获取要加载的模型名称
            if model_name is None:
                model_name = self.model_manager.get_selected_model()
            
            # 检查模型文件是否存在
            if not self.model_manager.model_exists(model_name):
                model_path = self.model_manager.get_model_path(model_name)
                QMessageBox.critical(None, "错误", f"YOLO模型文件不存在: {model_path}")
                return False
            
            model_path = self.model_manager.get_model_path(model_name)
            
            # 加载YOLO模型
            self.yolo_model = YOLO(model_path)
            self.current_model_name = model_name
            return True
        except Exception as e:
            QMessageBox.critical(None, "错误", f"加载YOLO模型失败: {str(e)}")
            return False
    
    def perform_yolo_prediction(self):
        """执行YOLO预测"""
        if not self.current_image:
            QMessageBox.warning(self, "警告", "请先选择一个图像")
            return
        
        # 加载YOLO模型（如果还未加载）
        if self.yolo_model is None:
            if not self.load_yolo_model():
                return
        
        try:
            # 禁用预测按钮，防止重复点击
            self.yolo_predict_button.setEnabled(False)
            self.yolo_predict_button.setText("⏳")
            
            # 将PIL图像转换为路径，因为YOLO接受文件路径
            if hasattr(self.current_yolo_label, 'image_path'):
                image_path = self.current_yolo_label.image_path
            else:
                QMessageBox.warning(self, "警告", "无法获取图像路径")
                return
            
            # 执行预测
            results = self.yolo_model(image_path, conf=self.confidence_threshold)
            
            # 解析预测结果
            self.yolo_predictions = []
            if results and len(results) > 0:
                for result in results:
                    if hasattr(result, 'boxes') and result.boxes is not None:
                        boxes = result.boxes
                        for i in range(len(boxes)):
                            # 获取边界框坐标（归一化）
                            box = boxes.xywhn[i].cpu().numpy()  # [center_x, center_y, width, height]
                            conf = boxes.conf[i].cpu().numpy()  # 置信度
                            cls = int(boxes.cls[i].cpu().numpy())  # 类别ID
                            
                            # 存储预测结果，格式为 [class_id, center_x, center_y, width, height, confidence]
                            self.yolo_predictions.append([cls, box[0], box[1], box[2], box[3], conf])
            
            # 显示预测结果
            self.show_predictions = True
            self.update_display_image(adjust_view=False)
            
            # 显示并启用预测操作按钮
            self._update_prediction_buttons_visibility()
            
            # 显示预测结果提示
            prediction_count = len(self.yolo_predictions)
            self._show_prediction_result(prediction_count)
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"YOLO预测失败: {str(e)}")
        finally:
            # 恢复预测按钮状态
            self.yolo_predict_button.setEnabled(True)
            self.yolo_predict_button.setText("🔍")
    
    def get_prediction_at_position(self, scene_pos):
        """查找点击位置的预测框索引
        
        Args:
            scene_pos: 场景中的点击位置
            
        Returns:
            预测框索引，如果未找到则返回None
        """
        if not self.yolo_predictions or not self.current_image:
            return None
        
        # 获取图像尺寸
        img_width, img_height = self.current_image.size
        
        # 获取点击位置
        pos_x, pos_y = scene_pos.x(), scene_pos.y()
        
        # 检查每个预测框
        for i, prediction in enumerate(self.yolo_predictions):
            class_id, center_x, center_y, width, height, confidence = prediction
            
            # 将归一化坐标转换为像素坐标
            x_center = center_x * img_width
            y_center = center_y * img_height
            box_width = width * img_width
            box_height = height * img_height
            
            # 计算左上和右下坐标
            x1 = x_center - (box_width / 2)
            y1 = y_center - (box_height / 2)
            x2 = x_center + (box_width / 2)
            y2 = y_center + (box_height / 2)
            
            # 检查点击位置是否在预测框内
            if x1 <= pos_x <= x2 and y1 <= pos_y <= y2:
                return i
        
        return None
    
    def show_prediction_context_menu(self, prediction_index, global_pos):
        """显示预测框的右键菜单
        
        Args:
            prediction_index: 预测框索引
            global_pos: 全局鼠标位置
        """
        if prediction_index is None or prediction_index >= len(self.yolo_predictions):
            return
        
        prediction = self.yolo_predictions[prediction_index]
        class_id, center_x, center_y, width, height, confidence = prediction
        
        # 创建右键菜单
        menu = QMenu(self)
        
        # 获取船舶类型名称
        ship_type = self.ship_types.get(str(class_id), f"类别{class_id}")
        
        # 添加菜单项
        add_action = menu.addAction(f"📝 追加到标签 ({ship_type} {confidence:.2f})")
        add_action.triggered.connect(lambda: self.add_prediction_to_labels(prediction_index))
        
        delete_action = menu.addAction(f"🗑️ 删除预测结果")
        delete_action.triggered.connect(lambda: self.delete_prediction(prediction_index))
        
        # 显示菜单
        menu.exec(global_pos)
    
    def add_prediction_to_labels(self, prediction_index):
        """将预测结果追加到当前标签文件
        
        Args:
            prediction_index: 要追加的预测框索引
        """
        if prediction_index is None or prediction_index >= len(self.yolo_predictions):
            return
        
        if not self.current_yolo_label:
            QMessageBox.warning(self, "警告", "没有可用的标签文件")
            return
        
        prediction = self.yolo_predictions[prediction_index]
        class_id, center_x, center_y, width, height, confidence = prediction
        
        # 使用信号机制添加标注框，与手动添加保持一致
        self.bbox_created.emit(class_id, center_x, center_y, width, height)
        
        # 从预测列表中移除已添加的预测
        self.yolo_predictions.pop(prediction_index)
        
        # 更新显示
        self.update_display_image(adjust_view=False)
        
        # 如果所有预测都被添加了，更新按钮状态
        if not self.yolo_predictions:
            self.show_predictions = False
            self._update_prediction_buttons_visibility()
    
    def delete_prediction(self, prediction_index):
        """删除指定的预测结果
        
        Args:
            prediction_index: 要删除的预测框索引
        """
        if prediction_index is None or prediction_index >= len(self.yolo_predictions):
            return
        
        # 从预测列表中移除
        self.yolo_predictions.pop(prediction_index)
        
        # 更新显示
        self.update_display_image(adjust_view=False)
        
        # 如果所有预测都被删除了，更新按钮状态
        if not self.yolo_predictions:
            self.show_predictions = False
            self._update_prediction_buttons_visibility()
    
    def accept_all_predictions(self):
        """接受所有YOLO预测结果，将它们添加到标签文件"""
        if not self.yolo_predictions or not self.current_yolo_label:
            return
        
        try:
            # 遍历所有预测结果并使用信号机制添加标注框
            for prediction in self.yolo_predictions[:]:  # 使用切片创建副本以避免修改时的问题
                class_id, center_x, center_y, width, height, confidence = prediction
                
                # 使用信号机制添加标注框，与手动添加保持一致
                self.bbox_created.emit(class_id, center_x, center_y, width, height)
            
            # 清空预测列表
            self.yolo_predictions = []
            self.show_predictions = False
            
            # 更新显示
            self.update_display_image(adjust_view=False)
            
            # 更新预测按钮状态
            self._update_prediction_buttons_visibility()
                
        except Exception as e:
            QMessageBox.critical(self, "错误", f"接受预测结果失败: {str(e)}")
    
    def reset_predictions(self):
        """重置YOLO预测结果"""
        self.yolo_predictions = []
        self.show_predictions = False
        
        # 更新预测按钮状态
        self._update_prediction_buttons_visibility()
        
        # 重新绘制图像（不显示预测结果）
        self.update_display_image(adjust_view=False)
    
    def _update_yolo_button_tooltip(self):
        """更新YOLO预测按钮的提示文本"""
        if self.current_model_name:
            tooltip = f"YOLO预测 (当前模型: {self.current_model_name})"
        else:
            selected_model = self.model_manager.get_selected_model()
            tooltip = f"YOLO预测 (模型: {selected_model})"
        
        self.yolo_predict_button.setToolTip(tooltip)
    
    def reset_yolo_model(self):
        """重置YOLO模型（当模型设置更改时调用）"""
        # 重置当前模型
        self.yolo_model = None
        self.current_model_name = None
        
        # 重置预测结果
        self.reset_predictions()
        
        # 更新预测按钮提示文本以显示当前模型
        self._update_yolo_button_tooltip()
    
    def _update_prediction_buttons_visibility(self):
        """根据预测结果状态更新预测操作按钮的可见性"""
        has_predictions = bool(self.yolo_predictions and self.show_predictions)
        
        # 根据是否有预测结果来显示/隐藏按钮
        self.accept_all_predictions_button.setVisible(has_predictions)
        self.reset_predictions_button.setVisible(has_predictions)
        
        # 重新定位按钮
        self._position_floating_buttons()
    
    def _show_prediction_result(self, count):
        """显示预测结果提示
        
        Args:
            count: 识别到的对象数量
        """
        if count == 0:
            self.prediction_result_label.setText("🔍  未识别到任何对象")
            self.prediction_result_label.setStyleSheet("""
                QLabel {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                        stop:0 rgba(255, 165, 0, 250), stop:1 rgba(255, 140, 0, 250));
                    color: white;
                    font-family: "Microsoft YaHei", "Segoe UI", Arial, sans-serif;
                    font-size: 18px;
                    font-weight: bold;
                    padding: 16px 28px;
                    border-radius: 25px;
                    border: 3px solid rgba(255, 255, 255, 220);
                    box-shadow: 0px 8px 16px rgba(0, 0, 0, 50);
                    text-shadow: 0px 2px 4px rgba(0, 0, 0, 100);
                }
            """)
        else:
            self.prediction_result_label.setText(f"🎯 识别到 {count} 个对象")
            self.prediction_result_label.setStyleSheet("""
                QLabel {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                        stop:0 rgba(34, 139, 34, 250), stop:1 rgba(50, 205, 50, 250));
                    color: white;
                    font-family: "Microsoft YaHei", "Segoe UI", Arial, sans-serif;
                    font-size: 18px;
                    font-weight: bold;
                    padding: 16px 28px;
                    border-radius: 25px;
                    border: 3px solid rgba(255, 255, 255, 220);
                    box-shadow: 0px 8px 16px rgba(0, 0, 0, 50);
                    text-shadow: 0px 2px 4px rgba(0, 0, 0, 100);
                }
            """)
        
        # 调整标签大小
        self.prediction_result_label.adjustSize()
        
        # 定位到视图中心上方
        self._position_prediction_result_label()
        
        # 显示标签
        self.prediction_result_label.setVisible(True)
        self.prediction_result_label.raise_()
        
        # 启动定时器，1秒后自动隐藏
        self.result_timer.start(1000)
    
    def _hide_prediction_result(self):
        """隐藏预测结果提示"""
        self.prediction_result_label.setVisible(False)
    
    def _position_prediction_result_label(self):
        """定位预测结果提示标签"""
        if not hasattr(self, 'prediction_result_label'):
            return
            
        # 获取图形视图的尺寸
        view_width = self.graphics_view.width()
        view_height = self.graphics_view.height()
        
        # 获取标签尺寸
        label_width = self.prediction_result_label.width()
        label_height = self.prediction_result_label.height()
        
        # 居中显示在视图上方1/8处
        x = (view_width - label_width) // 2
        y = view_height // 8
        
        self.prediction_result_label.move(x, y)
    
    def load_image(self, image_path, label_path=None):
        """加载图像和标签
        
        Args:
            image_path: 图像文件路径
            label_path: 标签文件路径（可选）
        """
        # 加载图像
        self.current_image = image_utils.load_image(image_path)
        if not self.current_image:
            return False
        
        # 转换为QPixmap对象
        self.current_pixmap = image_utils.pil_to_pixmap(self.current_image)
        
        # 加载标签数据
        if label_path and os.path.exists(label_path):
            self.current_yolo_label = YoloLabel(image_path, label_path)
        else:
            # 创建空标签对象
            labels_dir = os.path.dirname(label_path) if label_path else os.path.dirname(image_path)
            default_label_path = os.path.join(labels_dir, f"{os.path.splitext(os.path.basename(image_path))[0]}{config.LABEL_FILE_EXT}")
            self.current_yolo_label = YoloLabel(image_path, default_label_path)
        
        # 重置选中状态
        self.selected_bbox_index = -1
        
        # 切换图像时自动重置预测结果
        self.yolo_predictions = []
        self.show_predictions = False
        self._update_prediction_buttons_visibility()
        
        # 更新显示
        self.update_display_image()
        
        return True
    
    def update_display_image(self, adjust_view=True):
        """更新显示图像（包括绘制标签框和预测结果）"""
        if not self.current_image or not self.current_pixmap:
            return
        
        # 获取图像尺寸
        image_width, image_height = self.current_image.size
        
        # 创建带有边界框的图像
        if self.current_yolo_label and self.current_yolo_label.get_labels():
            # 获取标签数据
            labels = self.current_yolo_label.get_labels()
            
            # 绘制所有边界框
            self.current_pixmap_with_boxes = image_utils.draw_boxes_qt(
                self.current_pixmap, 
                labels,
                self.ship_types,
                (image_width, image_height)
            )
            
            # 如果有选中的边界框，使用特殊样式绘制
            if self.selected_bbox_index >= 0 and self.selected_bbox_index < len(labels):
                self.current_pixmap_with_boxes = image_utils.highlight_selected_box(
                    self.current_pixmap_with_boxes,
                    labels[self.selected_bbox_index],
                    self.selected_bbox_index,
                    (image_width, image_height)
                )
        else:
            # 没有标签，直接使用原始图像
            self.current_pixmap_with_boxes = QPixmap(self.current_pixmap)
        
        # 如果需要显示YOLO预测结果，叠加绘制
        if self.show_predictions and self.yolo_predictions:
            self.current_pixmap_with_boxes = self._draw_yolo_predictions(
                self.current_pixmap_with_boxes, 
                (image_width, image_height)
            )
        
        # 清除场景
        self.graphics_scene.clear()
        
        # 添加图像到场景
        self.graphics_scene.addPixmap(self.current_pixmap_with_boxes)
        
        # 设置场景矩形
        self.graphics_scene.setSceneRect(self.graphics_scene.itemsBoundingRect())
        
        # 只有在需要时才调整视图缩放
        if adjust_view:
            self.adjust_image_to_view()
        else:
            # 如果不调整视图，至少确保按钮位置正确
            self._position_floating_buttons()
    
    def _draw_yolo_predictions(self, pixmap, image_size):
        """在图像上绘制YOLO预测结果
        
        Args:
            pixmap: 要绘制的QPixmap
            image_size: 原始图像尺寸 (width, height)
            
        Returns:
            绘制了预测结果的QPixmap
        """
        if not self.yolo_predictions:
            return pixmap
        
        # 创建副本
        result = QPixmap(pixmap)
        painter = QPainter(result)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        img_width, img_height = image_size
        pixmap_width = pixmap.width()
        pixmap_height = pixmap.height()
        
        # 计算比例因子
        scale_factor = min(pixmap_width / 800, pixmap_height / 600)
        if scale_factor < 0.5:
            scale_factor = 0.5
        
        # 预处理标签信息和位置
        label_info_list = []
        occupied_regions = []  # 记录已占用的标签区域，避免重叠
        
        for i, prediction in enumerate(self.yolo_predictions):
            class_id, center_x, center_y, width, height, confidence = prediction
            class_id_int = int(class_id)
            
            # 将归一化坐标转换为像素坐标
            x_center = center_x * img_width
            y_center = center_y * img_height
            box_width = width * img_width
            box_height = height * img_height
            
            # 计算左上和右下坐标
            x1 = x_center - (box_width / 2)
            y1 = y_center - (box_height / 2)
            x2 = x_center + (box_width / 2)
            y2 = y_center + (box_height / 2)
            
            # 根据pixmap的当前大小进行适当缩放
            scale_x = pixmap.width() / img_width
            scale_y = pixmap.height() / img_height
            
            scaled_x1 = x1 * scale_x
            scaled_y1 = y1 * scale_y
            scaled_x2 = x2 * scale_x
            scaled_y2 = y2 * scale_y
            
            # 准备标签文本和样式
            ship_type = self.ship_types.get(str(class_id_int), f"类别{class_id_int}")
            label_text = f"{ship_type} {confidence:.2f}"
            
            # 设置字体
            from PySide6.QtGui import QFont, QFontMetrics
            font = QFont()
            font.setPointSizeF(max(9, int(10 * scale_factor)))
            font.setBold(True)
            
            # 计算文本尺寸
            font_metrics = QFontMetrics(font)
            text_width = font_metrics.horizontalAdvance(label_text)
            text_height = font_metrics.height()
            
            # 添加边距
            padding = max(4, int(4 * scale_factor))
            label_width = text_width + padding * 2
            label_height = text_height + padding
            
            # 智能计算标签位置，避免重叠
            label_x, label_y = self._calculate_smart_label_position(
                scaled_x1, scaled_y1, scaled_x2, scaled_y2,
                label_width, label_height, padding,
                pixmap_width, pixmap_height, occupied_regions
            )
            
            # 记录此标签占用的区域
            label_rect = QRectF(label_x, label_y, label_width, label_height)
            occupied_regions.append(label_rect)
            
            # 存储标签信息
            label_info_list.append({
                'bbox': (scaled_x1, scaled_y1, scaled_x2, scaled_y2),
                'label_rect': label_rect,
                'label_text': label_text,
                'font': font,
                'padding': padding,
                'prediction_color': QColor("#FF6B00"),
                'scale_factor': scale_factor
            })
        
        # 先绘制所有边界框
        for label_info in label_info_list:
            scaled_x1, scaled_y1, scaled_x2, scaled_y2 = label_info['bbox']
            prediction_color = label_info['prediction_color']
            scale_factor = label_info['scale_factor']
            
            # 绘制预测边界框（虚线）
            pen = QPen(prediction_color)
            pen.setWidth(max(1, int(2 * scale_factor)))
            pen.setStyle(Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            
            # 绘制边界框
            painter.drawRect(QRectF(scaled_x1, scaled_y1, scaled_x2 - scaled_x1, scaled_y2 - scaled_y1))
        
        # 再绘制所有标签（确保标签在边界框之上）
        for label_info in label_info_list:
            self._draw_prediction_label(painter, label_info)
        
        painter.end()
        return result
    
    def _calculate_smart_label_position(self, bbox_x1, bbox_y1, bbox_x2, bbox_y2, 
                                       label_width, label_height, padding,
                                       pixmap_width, pixmap_height, occupied_regions):
        """智能计算标签位置，避免与其他标签重叠
        
        Args:
            bbox_x1, bbox_y1, bbox_x2, bbox_y2: 边界框坐标
            label_width, label_height: 标签尺寸
            padding: 内边距
            pixmap_width, pixmap_height: 图像尺寸
            occupied_regions: 已占用的标签区域列表
            
        Returns:
            tuple: (label_x, label_y) 标签位置
        """
        # 候选位置列表：按优先级排序
        # 0: 上方中央, 1: 下方中央, 2: 左上, 3: 右上, 4: 左下, 5: 右下, 6: 左侧, 7: 右侧
        candidate_positions = [
            # 上方中央（默认位置）
            (bbox_x1 + (bbox_x2 - bbox_x1 - label_width) / 2, bbox_y1 - label_height - padding),
            # 下方中央
            (bbox_x1 + (bbox_x2 - bbox_x1 - label_width) / 2, bbox_y2 + padding),
            # 左上角
            (bbox_x1, bbox_y1 - label_height - padding),
            # 右上角
            (bbox_x2 - label_width, bbox_y1 - label_height - padding),
            # 左下角
            (bbox_x1, bbox_y2 + padding),
            # 右下角
            (bbox_x2 - label_width, bbox_y2 + padding),
            # 左侧中央
            (bbox_x1 - label_width - padding, bbox_y1 + (bbox_y2 - bbox_y1 - label_height) / 2),
            # 右侧中央
            (bbox_x2 + padding, bbox_y1 + (bbox_y2 - bbox_y1 - label_height) / 2),
        ]
        
        # 尝试每个候选位置
        for label_x, label_y in candidate_positions:
            # 边界检查和调整
            label_x = max(0, min(pixmap_width - label_width, label_x))
            label_y = max(0, min(pixmap_height - label_height, label_y))
            
            # 创建候选标签矩形
            candidate_rect = QRectF(label_x, label_y, label_width, label_height)
            
            # 检查是否与已有标签重叠
            overlapping = False
            for occupied_rect in occupied_regions:
                if candidate_rect.intersects(occupied_rect):
                    # 计算重叠面积比例
                    intersection = candidate_rect.intersected(occupied_rect)
                    overlap_ratio = (intersection.width() * intersection.height()) / (label_width * label_height)
                    
                    # 如果重叠面积超过30%，认为是重叠
                    if overlap_ratio > 0.3:
                        overlapping = True
                        break
            
            # 如果没有重叠，使用这个位置
            if not overlapping:
                return label_x, label_y
        
        # 如果所有候选位置都重叠，尝试偏移策略
        return self._find_offset_position(
            bbox_x1, bbox_y1, bbox_x2, bbox_y2,
            label_width, label_height, padding,
            pixmap_width, pixmap_height, occupied_regions
        )
    
    def _find_offset_position(self, bbox_x1, bbox_y1, bbox_x2, bbox_y2,
                             label_width, label_height, padding,
                             pixmap_width, pixmap_height, occupied_regions):
        """当标准位置都重叠时，寻找偏移位置
        
        Returns:
            tuple: (label_x, label_y) 标签位置
        """
        # 使用默认位置（上方中央）作为起点
        base_x = bbox_x1 + (bbox_x2 - bbox_x1 - label_width) / 2
        base_y = bbox_y1 - label_height - padding
        
        # 如果上方越界，使用下方
        if base_y < 0:
            base_y = bbox_y2 + padding
        
        # 尝试垂直偏移
        offset_step = label_height + padding
        max_attempts = 5
        
        for attempt in range(max_attempts):
            # 向上偏移
            test_y = base_y - (attempt + 1) * offset_step
            if test_y >= 0:
                test_x = max(0, min(pixmap_width - label_width, base_x))
                candidate_rect = QRectF(test_x, test_y, label_width, label_height)
                
                overlapping = False
                for occupied_rect in occupied_regions:
                    if candidate_rect.intersects(occupied_rect):
                        intersection = candidate_rect.intersected(occupied_rect)
                        overlap_ratio = (intersection.width() * intersection.height()) / (label_width * label_height)
                        if overlap_ratio > 0.2:  # 降低重叠阈值
                            overlapping = True
                            break
                
                if not overlapping:
                    return test_x, test_y
            
            # 向下偏移
            test_y = base_y + (attempt + 1) * offset_step
            if test_y + label_height <= pixmap_height:
                test_x = max(0, min(pixmap_width - label_width, base_x))
                candidate_rect = QRectF(test_x, test_y, label_width, label_height)
                
                overlapping = False
                for occupied_rect in occupied_regions:
                    if candidate_rect.intersects(occupied_rect):
                        intersection = candidate_rect.intersected(occupied_rect)
                        overlap_ratio = (intersection.width() * intersection.height()) / (label_width * label_height)
                        if overlap_ratio > 0.2:
                            overlapping = True
                            break
                
                if not overlapping:
                    return test_x, test_y
        
        # 如果垂直偏移也不行，尝试水平偏移
        for attempt in range(max_attempts):
            # 向左偏移
            test_x = base_x - (attempt + 1) * (label_width + padding)
            if test_x >= 0:
                test_y = max(0, min(pixmap_height - label_height, base_y))
                candidate_rect = QRectF(test_x, test_y, label_width, label_height)
                
                overlapping = False
                for occupied_rect in occupied_regions:
                    if candidate_rect.intersects(occupied_rect):
                        intersection = candidate_rect.intersected(occupied_rect)
                        overlap_ratio = (intersection.width() * intersection.height()) / (label_width * label_height)
                        if overlap_ratio > 0.2:
                            overlapping = True
                            break
                
                if not overlapping:
                    return test_x, test_y
            
            # 向右偏移
            test_x = base_x + (attempt + 1) * (label_width + padding)
            if test_x + label_width <= pixmap_width:
                test_y = max(0, min(pixmap_height - label_height, base_y))
                candidate_rect = QRectF(test_x, test_y, label_width, label_height)
                
                overlapping = False
                for occupied_rect in occupied_regions:
                    if candidate_rect.intersects(occupied_rect):
                        intersection = candidate_rect.intersected(occupied_rect)
                        overlap_ratio = (intersection.width() * intersection.height()) / (label_width * label_height)
                        if overlap_ratio > 0.2:
                            overlapping = True
                            break
                
                if not overlapping:
                    return test_x, test_y
        
        # 最终回退：使用边界限制的基础位置
        final_x = max(0, min(pixmap_width - label_width, base_x))
        final_y = max(0, min(pixmap_height - label_height, base_y))
        return final_x, final_y
    
    def _draw_prediction_label(self, painter, label_info):
        """绘制单个预测标签
        
        Args:
            painter: QPainter对象
            label_info: 标签信息字典
        """
        label_rect = label_info['label_rect']
        label_text = label_info['label_text']
        font = label_info['font']
        padding = label_info['padding']
        prediction_color = label_info['prediction_color']
        scale_factor = label_info['scale_factor']
        
        # 设置字体
        painter.setFont(font)
        
        # 创建半透明背景色
        bg_color = QColor(prediction_color)
        bg_color.setAlpha(200)
        
        # 绘制标签背景
        corner_radius = max(3, int(4 * scale_factor))
        painter.setPen(Qt.PenStyle.NoPen)
        from PySide6.QtGui import QBrush
        painter.setBrush(QBrush(bg_color))
        painter.drawRoundedRect(label_rect, corner_radius, corner_radius)
        
        # 添加白色边框增强可见性
        border_pen = QPen(QColor("white"))
        border_pen.setWidth(max(1, int(1 * scale_factor)))
        painter.setPen(border_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(label_rect, corner_radius, corner_radius)
        
        # 绘制文字
        painter.setPen(QColor("white"))
        text_rect = QRectF(
            label_rect.x() + padding,
            label_rect.y(),
            label_rect.width() - padding * 2,
            label_rect.height()
        )
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, label_text)
    
    def adjust_image_to_view(self):
        """根据当前视图大小调整图像显示"""
        if not hasattr(self, 'graphics_scene') or not self.graphics_scene.items():
            return
            
        pixmap_item = self.graphics_scene.items()[0]
        if isinstance(pixmap_item, QGraphicsPixmapItem):
            # 调整视图以适应场景内容，保持纵横比
            self.graphics_view.fitInView(
                pixmap_item.boundingRect(), 
                Qt.AspectRatioMode.KeepAspectRatio
            )
            
            # 更新场景范围确保包含整个图像
            self.graphics_scene.setSceneRect(pixmap_item.boundingRect())
            
            # 确保悬浮按钮依然位于正确位置
            self._position_floating_buttons()
    
    def _position_floating_buttons(self):
        """定位悬浮按钮的位置"""
        if not hasattr(self, 'reset_zoom_button'):
            return
        
        # 获取图形视图的尺寸
        view_width = self.graphics_view.width()
        view_height = self.graphics_view.height()
        
        # 定位重置缩放按钮（右上角）
        self.reset_zoom_button.move(view_width - self.reset_zoom_button.width() - 10, 10)
        
        # 定位YOLO预测按钮（重置缩放按钮下方）
        if hasattr(self, 'yolo_predict_button'):
            yolo_y = 10 + self.reset_zoom_button.height() + 8
            self.yolo_predict_button.move(
                view_width - self.yolo_predict_button.width() - 8, 
                yolo_y
            )
            

            
            # 当有预测结果时，在预测按钮左侧排列接受和删除按钮
            if hasattr(self, 'accept_all_predictions_button') and self.accept_all_predictions_button.isVisible():
                # 接受所有按钮（最左）
                accept_x = view_width - self.yolo_predict_button.width() - 8 - self.accept_all_predictions_button.width() - 4
                self.accept_all_predictions_button.move(accept_x, yolo_y)
                
                # 删除所有按钮（中间）
                if hasattr(self, 'reset_predictions_button') and self.reset_predictions_button.isVisible():
                    reset_x = accept_x - self.reset_predictions_button.width() - 4
                    self.reset_predictions_button.move(reset_x, yolo_y)
        
        # 确保按钮在最顶层
        self.reset_zoom_button.raise_()
        if hasattr(self, 'yolo_predict_button'):
            self.yolo_predict_button.raise_()
        if hasattr(self, 'accept_all_predictions_button'):
            self.accept_all_predictions_button.raise_()
        if hasattr(self, 'reset_predictions_button'):
            self.reset_predictions_button.raise_()
        
        # 重新定位预测结果标签（如果可见）
        if hasattr(self, 'prediction_result_label') and self.prediction_result_label.isVisible():
            self._position_prediction_result_label()
    
    def resizeEvent(self, event):
        """处理窗口大小变化事件"""
        super().resizeEvent(event)
        # 窗口大小变化时重新定位悬浮按钮
        self._position_floating_buttons()
    
    def showEvent(self, event):
        """处理窗口显示事件"""
        super().showEvent(event)
        # 窗口显示时定位悬浮按钮
        self._position_floating_buttons()
    
    def is_view_zoomed(self):
        """检测当前视图是否已缩放"""
        transform = self.graphics_view.transform()
        return transform.m11() > 1.01 or transform.m22() > 1.01
    
    def on_graphics_view_click(self, event):
        """图形视图点击事件处理"""
        if not self.current_image or not self.current_yolo_label:
            return
            
        # 将鼠标点击位置转换为场景坐标
        scene_pos = self.graphics_view.mapToScene(event.pos())
        
        # 获取标签
        labels = self.current_yolo_label.get_labels()
        img_width, img_height = self.current_image.size
        
        # 调整坐标以匹配原始图像坐标
        if self.current_pixmap_with_boxes:
            pixmap_width = self.current_pixmap_with_boxes.width()
            pixmap_height = self.current_pixmap_with_boxes.height()
            
            scale_x = pixmap_width / img_width
            scale_y = pixmap_height / img_height
            
            adjusted_x = scene_pos.x() / scale_x
            adjusted_y = scene_pos.y() / scale_y
            adjusted_pos = QPointF(adjusted_x, adjusted_y)
            
            # 处理右键点击
            if event.button() == Qt.MouseButton.RightButton:
                # 检查是否右键点击在预测框上
                if self.show_predictions and self.yolo_predictions:
                    prediction_index = self.get_prediction_at_position(adjusted_pos)
                    if prediction_index is not None:
                        global_pos = event.globalPos()
                        self.show_prediction_context_menu(prediction_index, global_pos)
                        return
                
                # 检查是否右键点击在标注框上，发射信号让标注框编辑器处理
                bbox_index = image_utils.get_bbox_at_position(
                    adjusted_pos, labels, (img_width, img_height), 
                    (self.graphics_view.width(), self.graphics_view.height())
                )
                if bbox_index is not None:
                    # 将视图坐标转换为全局坐标
                    global_pos = self.graphics_view.viewport().mapToGlobal(event.pos())
                    self.show_class_menu_requested.emit(bbox_index, event.pos())
                return
            
            # 处理绘制新标注框
            if self.is_drawing_bbox:
                self.drawing_start_pos = adjusted_pos
                return
            
            # 检查是否点击在边界框的角点上
            view_size = (self.graphics_view.width(), self.graphics_view.height())
            bbox_idx, corner_idx = image_utils.get_bbox_corner_at_position(
                adjusted_pos, labels, (img_width, img_height), view_size
            )
            
            if bbox_idx is not None and corner_idx is not None:
                # 开始拖动角点
                self.is_dragging = True
                self.dragging_bbox_index = bbox_idx
                self.dragging_point_index = corner_idx
                self.original_cursor_pos = adjusted_pos
                
                # 设置光标
                if corner_idx == 0 or corner_idx == 2:
                    self.graphics_view.setCursor(Qt.CursorShape.SizeFDiagCursor)
                else:
                    self.graphics_view.setCursor(Qt.CursorShape.SizeBDiagCursor)
                
                self.selected_bbox_index = bbox_idx
                self.bbox_selected.emit(bbox_idx)
                return
            
            # 检查是否点击在边界框的边线上
            bbox_idx, edge_idx = image_utils.get_bbox_edge_at_position(
                adjusted_pos, labels, (img_width, img_height), view_size
            )
            
            if bbox_idx is not None and edge_idx is not None:
                # 开始拖动边线
                self.is_dragging = True
                self.is_edge_dragging = True
                self.dragging_bbox_index = bbox_idx
                self.dragging_edge_index = edge_idx
                self.original_cursor_pos = adjusted_pos
                
                # 设置光标
                if edge_idx == 0 or edge_idx == 2:
                    self.graphics_view.setCursor(Qt.CursorShape.SizeVerCursor)
                else:
                    self.graphics_view.setCursor(Qt.CursorShape.SizeHorCursor)
                
                self.selected_bbox_index = bbox_idx
                self.bbox_selected.emit(bbox_idx)
                return
            
            # 检查是否在边界框内部
            bbox_index = image_utils.get_bbox_at_position(
                adjusted_pos, labels, (img_width, img_height), view_size
            )
            
            # 确保selected_bbox_index始终是整数，不是None
            self.selected_bbox_index = bbox_index if bbox_index is not None else -1
            if bbox_index is not None:
                self.bbox_selected.emit(bbox_index)
                
                # 如果视图已缩放，允许在标注框内拖动
                if self.is_view_zoomed() and event.button() == Qt.MouseButton.LeftButton:
                    self.is_panning = True
                    self.last_pan_position = event.pos()
                    self.graphics_view.setCursor(Qt.CursorShape.ClosedHandCursor)
                return
        
        # 如果视图已缩放且未执行其他操作，则启用平移
        if self.is_view_zoomed() and event.button() == Qt.MouseButton.LeftButton:
            self.is_panning = True
            self.last_pan_position = event.pos()
            self.graphics_view.setCursor(Qt.CursorShape.ClosedHandCursor)
    
    def on_graphics_view_move(self, event):
        """处理鼠标移动事件"""
        # 处理平移操作
        if self.is_panning and self.last_pan_position:
            delta = event.pos() - self.last_pan_position
            self.last_pan_position = event.pos()
            
            self.graphics_view.horizontalScrollBar().setValue(
                self.graphics_view.horizontalScrollBar().value() - delta.x())
            self.graphics_view.verticalScrollBar().setValue(
                self.graphics_view.verticalScrollBar().value() - delta.y())
            return
        
        # 处理绘制新标注框
        if self.is_drawing_bbox and self.drawing_start_pos:
            self._handle_drawing_bbox_move(event)
            return
        
        # 处理拖动标注框
        if self.is_dragging and self.dragging_bbox_index >= 0:
            self._handle_bbox_dragging(event)
            return
        
        # 更新鼠标光标
        self._update_cursor_for_position(event)
    
    def on_graphics_view_release(self, event):
        """处理鼠标释放事件"""
        # 重置平移状态
        if self.is_panning:
            self.is_panning = False
            self.last_pan_position = None
            
            if self.is_view_zoomed():
                self.graphics_view.setCursor(Qt.CursorShape.OpenHandCursor)
            else:
                self.graphics_view.setCursor(Qt.CursorShape.ArrowCursor)
            return
        
        # 处理新标注框创建
        if self.is_drawing_bbox and self.drawing_start_pos and self.drawing_current_pos:
            self._finish_drawing_bbox()
            return
        
        # 处理边界框拖动释放
        if self.is_dragging and self.dragging_bbox_index >= 0:
            self._finish_bbox_dragging()
        
        # 重置拖动状态
        self.is_dragging = False
        self.dragging_point_index = -1
        self.dragging_bbox_index = -1
        self.is_edge_dragging = False
        self.dragging_edge_index = -1
        self.original_cursor_pos = None
        
        # 根据缩放状态设置合适的光标
        if self.is_view_zoomed():
            self.graphics_view.setCursor(Qt.CursorShape.OpenHandCursor)
        else:
            self.graphics_view.setCursor(Qt.CursorShape.ArrowCursor)
    
    def _handle_drawing_bbox_move(self, event):
        """处理绘制标注框时的鼠标移动"""
        if not self.current_image or not self.current_pixmap_with_boxes:
            return
            
        # 将鼠标位置转换为场景坐标
        scene_pos = self.graphics_view.mapToScene(event.pos())
        
        # 获取图像尺寸
        img_width, img_height = self.current_image.size
        
        # 获取图像在场景中的缩放比例
        pixmap_width = self.current_pixmap_with_boxes.width()
        pixmap_height = self.current_pixmap_with_boxes.height()
        
        # 计算缩放比例
        scale_x = pixmap_width / img_width
        scale_y = pixmap_height / img_height
        
        # 调整坐标到图像空间
        current_x = scene_pos.x() / scale_x
        current_y = scene_pos.y() / scale_y
        
        # 确保坐标在图像范围内
        current_x = max(0, min(img_width, current_x))
        current_y = max(0, min(img_height, current_y))
        
        adjusted_pos = QPointF(current_x, current_y)
        
        # 更新当前鼠标位置
        self.drawing_current_pos = adjusted_pos
        
        # 计算临时边界框坐标
        start_x = self.drawing_start_pos.x()
        start_y = self.drawing_start_pos.y()
        current_x = self.drawing_current_pos.x()
        current_y = self.drawing_current_pos.y()
        
        # 计算临时边界框的左上和右下坐标
        x1 = min(start_x, current_x)
        y1 = min(start_y, current_y)
        x2 = max(start_x, current_x)
        y2 = max(start_y, current_y)
        
        # 使用临时边界框重绘图像
        temp_pixmap = QPixmap(self.current_pixmap)
        painter = QPainter(temp_pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # 设置绘制样式（虚线）
        pen = QPen(QColor("#FF0000"))  # 红色
        pen.setWidth(2)
        pen.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(pen)
        
        # 转换为场景坐标
        scene_x1 = x1 * scale_x
        scene_y1 = y1 * scale_y
        scene_x2 = x2 * scale_x
        scene_y2 = y2 * scale_y
        
        # 创建半透明填充
        fill_color = QColor(255, 0, 0, 40)  # 红色半透明填充
        painter.setBrush(fill_color)
        
        # 绘制临时边界框
        painter.drawRect(QRectF(scene_x1, scene_y1, scene_x2 - scene_x1, scene_y2 - scene_y1))
        
        # 添加外边框以增强可见性
        pen.setColor(QColor("#FFFFFF"))  # 白色外边框
        pen.setWidth(1)
        pen.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)  # 无填充
        painter.drawRect(QRectF(scene_x1-1, scene_y1-1, scene_x2 - scene_x1 + 2, scene_y2 - scene_y1 + 2))
        
        painter.end()
        
        # 清除场景并添加临时图像，但不重置视图
        self.graphics_scene.clear()
        self.graphics_scene.addPixmap(temp_pixmap)
        
        # 确保场景矩形包含整个图像
        self.graphics_scene.setSceneRect(temp_pixmap.rect())
    
    def _handle_bbox_dragging(self, event):
        """处理标注框拖动"""
        if not self.current_image or not self.current_yolo_label:
            return
            
        # 获取标签
        labels = self.current_yolo_label.get_labels()
        if self.dragging_bbox_index >= len(labels):
            return
            
        # 获取当前标签
        label = labels[self.dragging_bbox_index]
        if len(label) != 5:
            return
            
        # 将鼠标位置转换为场景坐标
        scene_pos = self.graphics_view.mapToScene(event.pos())
        
        # 获取图像尺寸
        img_width, img_height = self.current_image.size
        
        # 获取图像在场景中的缩放比例
        pixmap_width = self.current_pixmap_with_boxes.width()
        pixmap_height = self.current_pixmap_with_boxes.height()
        
        # 计算缩放比例
        scale_x = pixmap_width / img_width
        scale_y = pixmap_height / img_height
        
        # 调整坐标到图像空间
        current_x = scene_pos.x() / scale_x
        current_y = scene_pos.y() / scale_y
        
        # 确保坐标在图像范围内
        current_x = max(0, min(img_width, current_x))
        current_y = max(0, min(img_height, current_y))
        
        adjusted_pos = QPointF(current_x, current_y)
        
        # 获取当前标签的归一化坐标和尺寸
        class_id, center_x, center_y, width, height = label
        
        # 边界框的四个角点坐标（像素坐标）
        x_center = center_x * img_width
        y_center = center_y * img_height
        box_width = width * img_width
        box_height = height * img_height
        
        # 计算左上和右下坐标
        x1 = x_center - (box_width / 2)
        y1 = y_center - (box_height / 2)
        x2 = x_center + (box_width / 2)
        y2 = y_center + (box_height / 2)
        
        # 根据拖动的类型分别处理
        if self.is_edge_dragging:
            # 处理边线拖动
            edge_idx = self.dragging_edge_index
            
            if edge_idx == 0:  # 上边
                y1 = adjusted_pos.y()
            elif edge_idx == 1:  # 右边
                x2 = adjusted_pos.x()
            elif edge_idx == 2:  # 下边
                y2 = adjusted_pos.y()
            elif edge_idx == 3:  # 左边
                x1 = adjusted_pos.x()
            
            # 确保尺寸不为负数
            if x2 <= x1:
                x2 = x1 + 1
            if y2 <= y1:
                y2 = y1 + 1
            
            # 更新中心点和尺寸
            new_center_x = (x1 + x2) / 2 / img_width
            new_center_y = (y1 + y2) / 2 / img_height
            new_width = (x2 - x1) / img_width
            new_height = (y2 - y1) / img_height
        else:
            # 处理角点拖动
            corner_idx = self.dragging_point_index
            
            if corner_idx == 0:  # 左上
                x1 = adjusted_pos.x()
                y1 = adjusted_pos.y()
            elif corner_idx == 1:  # 右上
                x2 = adjusted_pos.x()
                y1 = adjusted_pos.y()
            elif corner_idx == 2:  # 右下
                x2 = adjusted_pos.x()
                y2 = adjusted_pos.y()
            elif corner_idx == 3:  # 左下
                x1 = adjusted_pos.x()
                y2 = adjusted_pos.y()
            
            # 确保尺寸不为负数
            if x2 <= x1:
                x2 = x1 + 1
            if y2 <= y1:
                y2 = y1 + 1
            
            # 更新中心点和尺寸
            new_center_x = (x1 + x2) / 2 / img_width
            new_center_y = (y1 + y2) / 2 / img_height
            new_width = (x2 - x1) / img_width
            new_height = (y2 - y1) / img_height
        
        # 更新标签
        self.current_yolo_label.update_label_coords(
            self.dragging_bbox_index, new_center_x, new_center_y, new_width, new_height
        )
        
        # 更新显示，不调整视图以保持当前缩放状态
        self.update_display_image(adjust_view=False)
    
    def _update_cursor_for_position(self, event):
        """根据鼠标位置更新光标"""
        if not self.current_image or not self.current_yolo_label:
            return
            
        # 如果正在拖动或绘制，不更新光标
        if self.is_dragging or self.is_drawing_bbox:
            return
            
        # 将鼠标位置转换为场景坐标
        scene_pos = self.graphics_view.mapToScene(event.pos())
        
        # 获取标签
        labels = self.current_yolo_label.get_labels()
        img_width, img_height = self.current_image.size
        
        # 调整坐标以匹配原始图像坐标
        if self.current_pixmap_with_boxes:
            pixmap_width = self.current_pixmap_with_boxes.width()
            pixmap_height = self.current_pixmap_with_boxes.height()
            
            scale_x = pixmap_width / img_width
            scale_y = pixmap_height / img_height
            
            adjusted_x = scene_pos.x() / scale_x
            adjusted_y = scene_pos.y() / scale_y
            adjusted_pos = QPointF(adjusted_x, adjusted_y)
            
            view_size = (self.graphics_view.width(), self.graphics_view.height())
            
            # 首先检查鼠标是否在角点上
            bbox_idx, corner_idx = image_utils.get_bbox_corner_at_position(
                adjusted_pos, labels, (img_width, img_height), view_size
            )
            
            if bbox_idx is not None and corner_idx is not None:
                # 鼠标在角点上，根据角点类型设置不同的对角线光标
                if corner_idx == 0 or corner_idx == 2:  # 左上角或右下角
                    self.graphics_view.setCursor(Qt.CursorShape.SizeFDiagCursor)
                else:  # 右上角或左下角
                    self.graphics_view.setCursor(Qt.CursorShape.SizeBDiagCursor)
            else:
                # 检查鼠标是否在边线上
                bbox_idx, edge_idx = image_utils.get_bbox_edge_at_position(
                    adjusted_pos, labels, (img_width, img_height), view_size
                )
                
                if bbox_idx is not None and edge_idx is not None:
                    # 根据边线类型设置光标形状
                    if edge_idx == 0 or edge_idx == 2:  # 上边或下边
                        self.graphics_view.setCursor(Qt.CursorShape.SizeVerCursor)
                    else:  # 左边或右边
                        self.graphics_view.setCursor(Qt.CursorShape.SizeHorCursor)
                elif self.is_panning:
                    # 如果正在平移，设置为手型光标
                    self.graphics_view.setCursor(Qt.CursorShape.ClosedHandCursor)
                elif self.is_view_zoomed():
                    # 如果视图被缩放且鼠标不在任何控件上，设置为打开的手型光标（提示可平移）
                    self.graphics_view.setCursor(Qt.CursorShape.OpenHandCursor)
                else:
                    # 其他情况恢复默认光标
                    self.graphics_view.setCursor(Qt.CursorShape.ArrowCursor)
    
    def _finish_drawing_bbox(self):
        """完成标注框绘制"""
        # 计算标注框坐标
        img_width, img_height = self.current_image.size
        
        start_x = self.drawing_start_pos.x()
        start_y = self.drawing_start_pos.y()
        current_x = self.drawing_current_pos.x()
        current_y = self.drawing_current_pos.y()
        
        # 计算标注框的左上和右下坐标
        x1 = min(start_x, current_x)
        y1 = min(start_y, current_y)
        x2 = max(start_x, current_x)
        y2 = max(start_y, current_y)
        
        # 确保有一定大小
        if (x2 - x1) < 5 or (y2 - y1) < 5:
            # 标注框太小，取消创建
            pass
        else:
            # 计算归一化的中心点和尺寸
            center_x = (x1 + x2) / 2 / img_width
            center_y = (y1 + y2) / 2 / img_height
            width = (x2 - x1) / img_width
            height = (y2 - y1) / img_height
            
            # 获取当前标注框数量，这将是新标注框的索引
            if self.current_yolo_label:
                new_bbox_index = len(self.current_yolo_label.get_labels())
                
                # 获取当前鼠标位置作为菜单显示位置
                cursor_pos = self.graphics_view.mapFromGlobal(QCursor.pos())
                
                # 如果鼠标不在视图内，使用视图中心点
                if not self.graphics_view.rect().contains(cursor_pos):
                    cursor_pos = QPoint(self.graphics_view.width() // 2, self.graphics_view.height() // 2)
                
                # 先发射创建信号（这会添加标注框到标签列表）
                self.bbox_created.emit(-1, center_x, center_y, width, height)
                
                # 然后发射信号请求显示类别菜单
                self.show_class_menu_requested.emit(new_bbox_index, cursor_pos)
        
        # 重置绘制状态
        self.is_drawing_bbox = False
        self.drawing_start_pos = None
        self.drawing_current_pos = None
        self.graphics_view.setCursor(Qt.CursorShape.ArrowCursor)
    
    def _finish_bbox_dragging(self):
        """完成标注框拖动"""
        # 发射修改信号
        if self.current_yolo_label and 0 <= self.dragging_bbox_index < len(self.current_yolo_label.get_labels()):
            labels = self.current_yolo_label.get_labels()
            label = labels[self.dragging_bbox_index]
            if len(label) == 5:
                class_id, center_x, center_y, width, height = label
                self.bbox_modified.emit(self.dragging_bbox_index, center_x, center_y, width, height)
    
    def start_drawing_bbox(self):
        """开始绘制标注框"""
        self.is_drawing_bbox = True
        self.drawing_start_pos = None
        self.drawing_current_pos = None
        self.graphics_view.setCursor(Qt.CursorShape.CrossCursor)
    
    def set_selected_bbox(self, bbox_index):
        """设置选中的标注框"""
        self.selected_bbox_index = bbox_index
        # 更新显示以高亮选中的标注框
        self.update_display_image(adjust_view=False)
    
    def get_current_labels(self):
        """获取当前标签列表"""
        if self.current_yolo_label:
            return self.current_yolo_label.get_labels()
        return []
    
    def clear_image(self):
        """清空当前图像显示"""
        self.current_image = None
        self.current_pixmap = None
        self.current_pixmap_with_boxes = None
        self.current_yolo_label = None
        self.selected_bbox_index = -1
        
        # 重置拖动状态
        self.is_dragging = False
        self.dragging_point_index = -1
        self.dragging_bbox_index = -1
        self.is_edge_dragging = False
        self.dragging_edge_index = -1
        self.original_cursor_pos = None
        
        # 重置绘制状态
        self.is_drawing_bbox = False
        self.drawing_start_pos = None
        self.drawing_current_pos = None
        
        # 重置平移状态
        self.is_panning = False
        self.last_pan_position = None
        
        # 重置YOLO预测状态
        self.reset_predictions()
        
        # 隐藏预测结果提示
        if hasattr(self, 'prediction_result_label'):
            self.prediction_result_label.setVisible(False)
        if hasattr(self, 'result_timer'):
            self.result_timer.stop()
        
        # 清空场景
        self.graphics_scene.clear()
        
        # 恢复默认光标
        self.graphics_view.setCursor(Qt.CursorShape.ArrowCursor) 