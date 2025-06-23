"""
自定义图形视图组件
提供增强的图像显示和交互功能
"""
from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QGraphicsView


class CustomGraphicsView(QGraphicsView):
    """自定义QGraphicsView类，用于更好地处理鼠标事件"""
    
    def __init__(self, parent=None):
        """初始化自定义视图"""
        super().__init__(parent)
        self.setMouseTracking(True)  # 启用鼠标跟踪
        
        # 设置自适应特性，使图像始终保持比例适应视图
        self.setRenderHint(QPainter.RenderHint.Antialiasing)  # 抗锯齿
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)  # 平滑像素图变换
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)  # 中心对齐
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)  # 全视口更新模式
        
        # 滚动条设置（保持不可见，但启用它们以支持平移功能）
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        # 启用拖动功能，但不使用Qt内置的拖动模式，我们自己实现
        self.setDragMode(QGraphicsView.DragMode.NoDrag) 
        
        # 设置场景调整策略
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        
        # 事件处理函数
        self.on_mouse_press = None
        self.on_mouse_move = None
        self.on_mouse_release = None
    
    def mousePressEvent(self, event):
        """鼠标按下事件"""
        super().mousePressEvent(event)
        if self.on_mouse_press:
            self.on_mouse_press(event)
    
    def mouseMoveEvent(self, event):
        """鼠标移动事件"""
        super().mouseMoveEvent(event)
        if self.on_mouse_move:
            self.on_mouse_move(event)
    
    def mouseReleaseEvent(self, event):
        """鼠标释放事件"""
        super().mouseReleaseEvent(event)
        if self.on_mouse_release:
            self.on_mouse_release(event)

    def wheelEvent(self, event):
        """处理鼠标滚轮事件以进行缩放"""
        zoom_in_factor = 1.15
        zoom_out_factor = 1.0 / zoom_in_factor

        if event.angleDelta().y() > 0:
            # 向上滚动，放大
            self.scale(zoom_in_factor, zoom_in_factor)
        else:
            # 向下滚动，缩小
            self.scale(zoom_out_factor, zoom_out_factor)
        
        event.accept()  # 接受事件，防止传递给父控件 