"""
图像处理工具模块
包含图像加载、缩放和绘制标签框等功能
"""
import os
from typing import List, Tuple, Optional

from PIL import Image, ImageDraw
from PySide6.QtCore import Qt, QPointF, QRectF
from PySide6.QtGui import QImage, QPixmap, QPainter, QPen, QColor, QFont, QBrush, QFontMetrics

import config


def load_image(image_path: str) -> Optional[Image.Image]:
    """
    加载图像文件
    
    Args:
        image_path: 图像文件路径
        
    Returns:
        PIL Image对象，如果加载失败则返回None
    """
    try:
        if os.path.exists(image_path):
            return Image.open(image_path)
        return None
    except Exception as e:
        print(f"加载图像时出错: {e}")
        return None

def resize_image(image: Image.Image, size: Tuple[int, int]) -> Image.Image:
    """
    调整图像大小，保持原始纵横比
    
    Args:
        image: 原始图像
        size: 目标大小 (width, height)
        
    Returns:
        调整大小后的图像
    """
    if image is None:
        return None
    
    img_width, img_height = image.size
    target_width, target_height = size
    
    # 计算缩放比例
    width_ratio = target_width / img_width
    height_ratio = target_height / img_height
    ratio = min(width_ratio, height_ratio)
    
    # 计算新尺寸
    new_width = int(img_width * ratio)
    new_height = int(img_height * ratio)
    
    # 调整图像大小
    return image.resize((new_width, new_height), Image.LANCZOS)

def pil_to_pixmap(pil_image: Image.Image) -> QPixmap:
    """
    将PIL图像转换为Qt QPixmap
    
    Args:
        pil_image: PIL图像对象
        
    Returns:
        Qt QPixmap对象
    """
    if pil_image is None:
        return None
    
    # 确保图像是RGB或RGBA模式
    if pil_image.mode != "RGBA" and pil_image.mode != "RGB":
        pil_image = pil_image.convert("RGBA")
    
    # 获取图像尺寸和格式
    width, height = pil_image.size
    format = QImage.Format.Format_RGBA8888 if pil_image.mode == "RGBA" else QImage.Format.Format_RGB888
    
    # 将PIL图像转换为bytes
    bytes_per_line = 4 * width if pil_image.mode == "RGBA" else 3 * width
    img_data = pil_image.tobytes("raw", pil_image.mode)
    
    # 创建QImage
    q_image = QImage(img_data, width, height, bytes_per_line, format)
    
    # 返回QPixmap
    return QPixmap.fromImage(q_image)

def create_thumbnail(image: Image.Image) -> QPixmap:
    """
    创建缩略图
    
    Args:
        image: 原始图像
        
    Returns:
        Qt QPixmap对象的缩略图
    """
    if image is None:
        return None
    
    thumbnail = image.copy()
    thumbnail.thumbnail(config.THUMBNAIL_SIZE, Image.LANCZOS)
    return pil_to_pixmap(thumbnail)

def draw_boxes(image: Image.Image, labels: List[List[float]], ship_types: dict) -> Image.Image:
    """
    在图像上绘制检测框
    
    Args:
        image: 原始图像
        labels: 标签列表，每个元素为 [class_id, center_x, center_y, width, height]
        ship_types: 船舶类型字典，键为class_id，值为类型名称
        
    Returns:
        绘制了检测框的图像
    """
    if image is None or not labels:
        return image
    
    # 创建副本，避免修改原始图像
    draw_image = image.copy()
    draw = ImageDraw.Draw(draw_image)
    
    img_width, img_height = image.size
    
    for i, label in enumerate(labels):
        if len(label) != 5:
            continue
        
        class_id, center_x, center_y, width, height = label
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
        
        # 获取颜色
        color_idx = class_id_int % len(config.BOX_COLORS)
        box_color = config.BOX_COLORS[color_idx]
        
        # 绘制边界框
        draw.rectangle([x1, y1, x2, y2], outline=box_color, width=2)
        
        # 获取船舶类型名称
        ship_type = ship_types.get(str(class_id_int), f"未知类型({class_id_int})")
        
        # 绘制标签文本背景 - 修复坐标顺序问题
        text_height = 16
        # 将标签绘制在边界框上方
        draw.rectangle([x1, y1 - text_height, x1 + len(ship_type) * 7 + 4, y1], fill=box_color)
        draw.text((x1 + 2, y1 - text_height + 2), ship_type, fill="white")
    
    return draw_image

def draw_boxes_qt(pixmap: QPixmap, labels: List[List[float]], ship_types: dict, 
                 original_size: Tuple[int, int]) -> QPixmap:
    """
    在Qt Pixmap上绘制检测框
    
    Args:
        pixmap: 原始QPixmap
        labels: 标签列表，每个元素为 [class_id, center_x, center_y, width, height]
        ship_types: 船舶类型字典，键为class_id，值为类型名称
        original_size: 原始图像尺寸 (width, height)
        
    Returns:
        绘制了检测框的QPixmap
    """
    if pixmap is None or not labels:
        return pixmap
    
    # 创建副本，避免修改原始图像
    result = QPixmap(pixmap)
    painter = QPainter(result)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    
    img_width, img_height = original_size
    pixmap_width = pixmap.width()
    pixmap_height = pixmap.height()
    
    # 计算比例因子，用于调整标签文本和控制点大小
    # 使用最小尺寸维度作为基准以保持一致性
    scale_factor = min(pixmap_width / 800, pixmap_height / 600)
    if scale_factor < 0.5:  # 设置最小缩放阈值
        scale_factor = 0.5
    
    for i, label in enumerate(labels):
        if len(label) != 5:
            continue
        
        class_id, center_x, center_y, width, height = label
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
        
        # 获取颜色
        color_idx = class_id_int % len(config.BOX_COLORS)
        box_color_str = config.BOX_COLORS[color_idx]
        qt_color = QColor(box_color_str)
        
        # 重要：每次绘制新框前重置画刷，确保没有填充
        painter.setBrush(Qt.BrushStyle.NoBrush)
        
        # 设置画笔，根据图像大小调整边框宽度
        pen_width = max(1, int(3 * scale_factor))
        pen = QPen(qt_color)
        pen.setWidth(pen_width)
        painter.setPen(pen)
        
        # 绘制边界框
        painter.drawRect(QRectF(scaled_x1, scaled_y1, scaled_x2 - scaled_x1, scaled_y2 - scaled_y1))
        
        # 获取船舶类型名称
        ship_type = ship_types.get(str(class_id_int), f"未知类型({class_id_int})")
        
        # ----- 开始优化标签文本渲染部分 -----
        # 设置字体 - 使用适当的字体大小
        font = QFont()
        font.setPointSizeF(max(9, int(10 * scale_factor)))
        font.setBold(True)  # 设置为粗体
        painter.setFont(font)
        
        # 使用QFontMetrics精确计算文本尺寸
        font_metrics = QFontMetrics(font)
        text_width = font_metrics.horizontalAdvance(ship_type)
        text_height = font_metrics.height()
        
        # 添加边距，使文本不会贴边显示
        padding = max(4, int(4 * scale_factor))
        label_width = text_width + padding * 2
        label_height = text_height + padding
        
        # 计算标签位置 - 默认在边界框上方
        label_x = scaled_x1
        label_y = scaled_y1 - label_height - padding
        
        # 检查标签是否会超出图像顶部边界，如果是则放在边界框下方
        if label_y < 0:
            label_y = scaled_y2 + padding
        
        # 检查标签是否会超出图像右侧边界，如果是则向左调整
        if label_x + label_width > pixmap_width:
            label_x = pixmap_width - label_width
        
        # 确保标签不会超出左侧边界
        if label_x < 0:
            label_x = 0
        
        # 创建标签矩形
        label_rect = QRectF(label_x, label_y, label_width, label_height)
        
        # 创建半透明背景色
        bg_color = QColor(qt_color)
        bg_color.setAlpha(220)  # 设置透明度 (0-255)
        
        # 绘制标签背景 - 使用圆角矩形
        corner_radius = max(3, int(4 * scale_factor))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(bg_color))
        painter.drawRoundedRect(label_rect, corner_radius, corner_radius)
        
        # 设置文字颜色
        painter.setPen(QColor("white"))
        
        # 绘制文字 - 考虑padding使文本居中显示
        text_rect = QRectF(
            label_x + padding, 
            label_y, 
            label_width - padding * 2, 
            label_height
        )
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, ship_type)
        # ----- 结束优化标签文本渲染部分 -----
        
        # 动态调整角点大小
        corner_size = max(4, int(8 * scale_factor))
        
        # 设置角点画笔和画刷
        painter.setPen(Qt.PenStyle.NoPen)  # 无边框
        painter.setBrush(QBrush(QColor("white")))  # 白色填充
        
        # 绘制四个角点（左上、右上、右下、左下）
        # 左上角
        painter.drawRect(QRectF(scaled_x1 - corner_size/2, scaled_y1 - corner_size/2, corner_size, corner_size))
        
        # 右上角
        painter.drawRect(QRectF(scaled_x2 - corner_size/2, scaled_y1 - corner_size/2, corner_size, corner_size))
        
        # 右下角
        painter.drawRect(QRectF(scaled_x2 - corner_size/2, scaled_y2 - corner_size/2, corner_size, corner_size))
        
        # 左下角
        painter.drawRect(QRectF(scaled_x1 - corner_size/2, scaled_y2 - corner_size/2, corner_size, corner_size))
        
        # 在角点上添加边框，提高可见性
        painter.setPen(QPen(qt_color, max(1, int(1.5 * scale_factor))))  # 动态调整边框宽度
        
        # 左上角
        painter.drawRect(QRectF(scaled_x1 - corner_size/2, scaled_y1 - corner_size/2, corner_size, corner_size))
        
        # 右上角
        painter.drawRect(QRectF(scaled_x2 - corner_size/2, scaled_y1 - corner_size/2, corner_size, corner_size))
        
        # 右下角
        painter.drawRect(QRectF(scaled_x2 - corner_size/2, scaled_y2 - corner_size/2, corner_size, corner_size))
        
        # 左下角
        painter.drawRect(QRectF(scaled_x1 - corner_size/2, scaled_y2 - corner_size/2, corner_size, corner_size))
    
    # 完成绘制
    painter.end()
    
    return result

def get_bbox_at_position(scene_pos: QPointF, labels: List[List[float]], 
                         image_size: Tuple[int, int], view_size: Tuple[int, int]) -> Optional[int]:
    """
    查找点击位置的边界框索引 (Qt版本)
    
    Args:
        scene_pos: 场景中的点击位置
        labels: 标签列表
        image_size: 原始图像尺寸 (width, height)
        view_size: 视图尺寸 (width, height)
        
    Returns:
        边界框索引，如果未找到则返回None
    """
    if not labels:
        return None
    
    # 获取图像尺寸
    img_width, img_height = image_size
    
    # 获取点击位置
    pos_x, pos_y = scene_pos.x(), scene_pos.y()
    
    # 检查每个边界框
    for i, label in enumerate(labels):
        if len(label) != 5:
            continue
        
        class_id, center_x, center_y, width, height = label
        
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
        
        # 检查点击位置是否在边界框内
        if x1 <= pos_x <= x2 and y1 <= pos_y <= y2:
            return i
    
    return None 

def get_bbox_corner_at_position(scene_pos: QPointF, labels: List[List[float]], 
                           image_size: Tuple[int, int], view_size: Tuple[int, int]) -> Tuple[Optional[int], Optional[int]]:
    """
    查找点击位置是否在边界框的角点上
    
    Args:
        scene_pos: 场景中的点击位置
        labels: 标签列表
        image_size: 原始图像尺寸 (width, height)
        view_size: 视图尺寸 (width, height)
        
    Returns:
        (边界框索引, 角点索引)，如果未找到则返回(None, None)
        角点索引: 0=左上, 1=右上, 2=右下, 3=左下
    """
    if not labels:
        return None, None
    
    # 获取图像尺寸
    img_width, img_height = image_size
    
    # 获取点击位置
    pos_x, pos_y = scene_pos.x(), scene_pos.y()
    
    # 角点检测的敏感度半径（像素）- 增加敏感度
    corner_sensitivity = 15
    
    # 检查每个边界框
    for i, label in enumerate(labels):
        if len(label) != 5:
            continue
        
        class_id, center_x, center_y, width, height = label
        
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
        
        # 检查点击位置是否在边界框的四个角点附近
        # 左上角 (0)
        if abs(pos_x - x1) <= corner_sensitivity and abs(pos_y - y1) <= corner_sensitivity:
            return i, 0
        
        # 右上角 (1)
        if abs(pos_x - x2) <= corner_sensitivity and abs(pos_y - y1) <= corner_sensitivity:
            return i, 1
        
        # 右下角 (2)
        if abs(pos_x - x2) <= corner_sensitivity and abs(pos_y - y2) <= corner_sensitivity:
            return i, 2
        
        # 左下角 (3)
        if abs(pos_x - x1) <= corner_sensitivity and abs(pos_y - y2) <= corner_sensitivity:
            return i, 3
    
    return None, None

def get_bbox_edge_at_position(scene_pos: QPointF, labels: List[List[float]], 
                          image_size: Tuple[int, int], view_size: Tuple[int, int]) -> Tuple[Optional[int], Optional[int]]:
    """
    查找点击位置是否在边界框的边线上
    
    Args:
        scene_pos: 场景中的点击位置
        labels: 标签列表
        image_size: 原始图像尺寸 (width, height)
        view_size: 视图尺寸 (width, height)
        
    Returns:
        (边界框索引, 边线索引)，如果未找到则返回(None, None)
        边线索引: 0=上, 1=右, 2=下, 3=左
    """
    if not labels:
        return None, None
    
    # 获取图像尺寸
    img_width, img_height = image_size
    
    # 获取点击位置
    pos_x, pos_y = scene_pos.x(), scene_pos.y()
    
    # 边线检测的敏感度（像素）
    edge_sensitivity = 10
    
    # 检查每个边界框
    for i, label in enumerate(labels):
        if len(label) != 5:
            continue
        
        class_id, center_x, center_y, width, height = label
        
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
        
        # 检查点击位置是否在边界框的四条边线附近
        
        # 上边线 (0)
        if abs(pos_y - y1) <= edge_sensitivity and x1 <= pos_x <= x2:
            return i, 0
        
        # 右边线 (1)
        if abs(pos_x - x2) <= edge_sensitivity and y1 <= pos_y <= y2:
            return i, 1
        
        # 下边线 (2)
        if abs(pos_y - y2) <= edge_sensitivity and x1 <= pos_x <= x2:
            return i, 2
        
        # 左边线 (3)
        if abs(pos_x - x1) <= edge_sensitivity and y1 <= pos_y <= y2:
            return i, 3
    
    return None, None 

def highlight_selected_box(pixmap: QPixmap, label: List[float], bbox_index: int, 
                      original_size: Tuple[int, int]) -> QPixmap:
    """
    高亮显示选中的边界框
    
    Args:
        pixmap: 已绘制了所有边界框的QPixmap
        label: 选中的标签数据，格式为 [class_id, center_x, center_y, width, height]
        bbox_index: 边界框索引
        original_size: 原始图像尺寸 (width, height)
        
    Returns:
        高亮了选中边界框的QPixmap
    """
    if pixmap is None or not label or len(label) != 5:
        return pixmap
    
    # 创建副本，避免修改原始图像
    result = QPixmap(pixmap)
    painter = QPainter(result)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    
    img_width, img_height = original_size
    pixmap_width = pixmap.width()
    pixmap_height = pixmap.height()
    
    # 解析标签数据
    class_id, center_x, center_y, width, height = label
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
    
    # 创建选中边界框的特殊样式
    # 获取颜色索引，但使用更突出的颜色显示选中状态
    select_color = QColor("yellow")  # 高亮色
    pen = QPen(select_color)
    pen.setWidth(3)  # 加粗边框宽度
    pen.setStyle(Qt.PenStyle.DashLine)  # 使用虚线样式
    painter.setPen(pen)
    
    # 重要：确保高亮框没有填充
    painter.setBrush(Qt.BrushStyle.NoBrush)
    
    # 绘制选中的边界框
    painter.drawRect(QRectF(scaled_x1, scaled_y1, scaled_x2 - scaled_x1, scaled_y2 - scaled_y1))
    
    # 绘制控制点
    point_size = 6  # 控制点大小
    control_points = [
        QPointF(scaled_x1, scaled_y1),  # 左上
        QPointF(scaled_x2, scaled_y1),  # 右上
        QPointF(scaled_x2, scaled_y2),  # 右下
        QPointF(scaled_x1, scaled_y2)   # 左下
    ]
    
    # 设置控制点笔和画刷
    painter.setPen(QPen(Qt.GlobalColor.red, 2))
    painter.setBrush(QBrush(Qt.GlobalColor.white))
    
    # 绘制控制点
    for point in control_points:
        painter.drawRect(QRectF(
            point.x() - point_size / 2,
            point.y() - point_size / 2,
            point_size,
            point_size
        ))
    
    # 结束绘制
    painter.end()
    
    return result 