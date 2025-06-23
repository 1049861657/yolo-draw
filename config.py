"""
YOLO船舶标注工具的配置文件
包含全局设置和预设值
"""
import os
import json

# 应用设置
APP_NAME = "YOLO船舶标注工具"
APP_VERSION = "1.4.0"
APP_VERSION_FULL = "1.0.0.0"  # Windows格式版本号
APP_WIDTH = 1200
APP_HEIGHT = 800

# 默认路径
DEFAULT_SOURCE_DIR = "F:/yolo资源/测试资源/油轮"  # 指向包含images和labels子文件夹的父目录
DEFAULT_TARGET_DIR = "F:/yolo资源/测试资源/result"

# 构建资源文件的路径
ship_types_path = os.path.join('resources', 'ship_types.json')

def get_ship_types():
    """获取船舶类型列表"""
    with open(ship_types_path, 'r', encoding='utf-8') as f:
        return json.load(f)

# 图像设置
THUMBNAIL_SIZE = (100, 100)  # 缩略图大小
IMAGE_DISPLAY_SIZE = (800, 600)  # 显示图像的大小

# 标签框显示设置
BOX_COLORS = [
    "#FF0000",  # 红色
    "#00FF00",  # 绿色
    "#0000FF",  # 蓝色
    "#FFFF00",  # 黄色
    "#FF00FF",  # 紫色
    "#00FFFF",  # 青色
    "#FFA500",  # 橙色
    "#800080",  # 紫罗兰
    "#008000",  # 深绿色
    "#800000",  # 深红色
    "#008080",  # 青灰色
    "#C0C0C0",  # 银色
]


# 文件格式
SUPPORTED_IMAGE_FORMATS = ['.jpg', '.jpeg', '.png', '.bmp']
LABEL_FILE_EXT = '.txt' 

# YOLO模型相关配置
YOLO_MODELS_DIR = "pt"  # YOLO模型文件目录
DEFAULT_YOLO_MODEL = "Fuck5.pt"  # 默认YOLO模型文件名
SETTINGS_FILE = "settings.json"  # 用户设置文件 