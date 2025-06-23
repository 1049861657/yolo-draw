"""
为应用程序创建一个简单的图标
"""
from PIL import Image, ImageDraw
import os

def create_icon():
    """创建一个简单的船舶图标"""
    # 创建一个新的RGBA图像，尺寸为256x256像素
    img = Image.new('RGBA', (256, 256), color=(255, 255, 255, 0))
    draw = ImageDraw.Draw(img)
    
    # 绘制一个简单的船形状（简化版）
    # 船体
    draw.polygon([(50, 150), (206, 150), (180, 200), (76, 200)], fill=(0, 83, 156))
    # 上层建筑
    draw.rectangle((100, 100, 156, 150), fill=(220, 220, 220))
    # 烟囱
    draw.rectangle((120, 80, 136, 110), fill=(180, 40, 40))
    
    # 确保目录存在
    if not os.path.exists('resources'):
        os.makedirs('resources')
    
    # 保存为ICO格式
    img.save('resources/icon.ico', format='ICO', sizes=[(256, 256)])
    print("图标已创建: resources/icon.ico")

if __name__ == "__main__":
    create_icon() 