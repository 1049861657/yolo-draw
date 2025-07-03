"""
标注速度统计组件
提供标注速度的统计、显示和更新功能
"""
import time
from collections import deque
from PySide6.QtCore import QTimer, QObject, Signal
from PySide6.QtWidgets import QLabel


class AnnotationSpeedTracker(QObject):
    """标注速度统计器"""
    
    # 信号：速度更新时发出
    speed_updated = Signal(float, int)  # (当前速度, 总标注数)
    
    def __init__(self, parent=None):
        """初始化标注速度统计器"""
        super().__init__(parent)
        
        # 标注时间记录队列（最多保存最近20次标注的时间）
        self.annotation_times = deque(maxlen=20)
        
        # 标注计数器
        self.total_annotations = 0
        self.session_start_time = time.time()
        
        # 创建定时器用于更新速度显示
        self.speed_update_timer = QTimer()
        self.speed_update_timer.timeout.connect(self._update_speed)
        self.speed_update_timer.start(1000)  # 每秒更新一次
    
    def record_annotation(self, count=1):
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
    
    def _update_speed(self):
        """更新标注速度并发出信号"""
        current_time = time.time()
        
        # 计算实时速度（最近1分钟内的标注）
        realtime_speed = 0.0
        recent_annotations = [t for t in self.annotation_times if current_time - t <= 60.0]
        if len(recent_annotations) >= 2:
            time_span = current_time - recent_annotations[0]
            if time_span > 0:
                realtime_speed = len(recent_annotations) / time_span
        
        # 发出速度更新信号
        self.speed_updated.emit(realtime_speed, self.total_annotations)
    
    def get_current_speed(self):
        """获取当前标注速度
        
        Returns:
            tuple: (当前速度, 总标注数)
        """
        current_time = time.time()
        
        # 计算实时速度（最近1分钟内的标注）
        realtime_speed = 0.0
        recent_annotations = [t for t in self.annotation_times if current_time - t <= 60.0]
        if len(recent_annotations) >= 2:
            time_span = current_time - recent_annotations[0]
            if time_span > 0:
                realtime_speed = len(recent_annotations) / time_span
        
        return realtime_speed, self.total_annotations
    
    def reset_statistics(self):
        """重置统计数据"""
        self.annotation_times.clear()
        self.total_annotations = 0
        self.session_start_time = time.time()
    
    def stop_tracking(self):
        """停止速度跟踪"""
        if self.speed_update_timer.isActive():
            self.speed_update_timer.stop()
    
    def start_tracking(self):
        """开始速度跟踪"""
        if not self.speed_update_timer.isActive():
            self.speed_update_timer.start(1000)


class AnnotationSpeedDisplay(QLabel):
    """标注速度显示组件"""
    
    def __init__(self, parent=None):
        """初始化标注速度显示组件"""
        super().__init__(parent)
        
        # 初始化显示
        self.setText("🚀 标注速度: 0.0 图片/秒")
        self._update_style(0.0)
    
    def update_speed_display(self, speed, total_annotations):
        """更新速度显示
        
        Args:
            speed: 当前速度（图片/秒）
            total_annotations: 总标注数
        """
        # 根据速度选择不同的图标
        icon = self._get_speed_icon(speed)
        
        # 更新显示文本
        speed_text = f"{icon} 标注速度: {speed:.1f} 图片/秒"
        if total_annotations > 0:
            speed_text += f" (总计: {total_annotations})"
        
        self.setText(speed_text)
        self._update_style(speed)
    
    def _get_speed_icon(self, speed):
        """根据速度获取对应图标
        
        Args:
            speed: 当前速度
            
        Returns:
            str: 对应的图标
        """
        if speed >= 2.0:
            return "🚀"  # 超快
        elif speed >= 1.0:
            return "⚡"  # 快速
        elif speed >= 0.5:
            return "🎯"  # 中等
        elif speed > 0:
            return "🐌"  # 慢速
        else:
            return "💤"  # 无活动
    
    def _update_style(self, speed):
        """根据速度更新样式
        
        Args:
            speed: 当前速度
        """
        # 根据速度选择不同的颜色
        if speed >= 2.0:
            color = "#FF6B35"  # 橙红色 - 超快
            bg_color = "rgba(255, 107, 53, 0.15)"
        elif speed >= 1.0:
            color = "#2E8B57"  # 海绿色 - 快速
            bg_color = "rgba(46, 139, 87, 0.15)"
        elif speed >= 0.5:
            color = "#4169E1"  # 皇家蓝 - 中等
            bg_color = "rgba(65, 105, 225, 0.15)"
        elif speed > 0:
            color = "#8B4513"  # 马鞍棕 - 慢速
            bg_color = "rgba(139, 69, 19, 0.15)"
        else:
            color = "#696969"  # 暗灰色 - 无活动
            bg_color = "rgba(105, 105, 105, 0.15)"
        
        # 更新样式
        self.setStyleSheet(f"""
            QLabel {{
                color: {color};
                font-weight: bold;
                padding: 2px 8px;
                border: 1px solid {color};
                border-radius: 3px;
                background-color: {bg_color};
            }}
        """)


class AnnotationSpeedWidget(QObject):
    """标注速度完整组件，包含统计器和显示器"""
    
    def __init__(self, parent=None):
        """初始化标注速度组件"""
        super().__init__(parent)
        
        # 创建统计器和显示器
        self.tracker = AnnotationSpeedTracker(self)
        self.display = AnnotationSpeedDisplay(parent)
        
        # 连接信号
        self.tracker.speed_updated.connect(self.display.update_speed_display)
    
    def record_annotation(self, count=1):
        """记录标注操作
        
        Args:
            count: 标注的图片数量
        """
        self.tracker.record_annotation(count)
    
    def get_display_widget(self):
        """获取显示组件
        
        Returns:
            AnnotationSpeedDisplay: 显示组件
        """
        return self.display
    
    def get_current_speed(self):
        """获取当前标注速度
        
        Returns:
            tuple: (当前速度, 总标注数)
        """
        return self.tracker.get_current_speed()
    
    def reset_statistics(self):
        """重置统计数据"""
        self.tracker.reset_statistics()
    
    def stop_tracking(self):
        """停止速度跟踪"""
        self.tracker.stop_tracking()
    
    def start_tracking(self):
        """开始速度跟踪"""
        self.tracker.start_tracking() 