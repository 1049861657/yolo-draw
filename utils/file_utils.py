"""
文件操作工具模块
包含文件读写、查找匹配文件、文件移动等功能
"""
import os
import shutil
from typing import List, Tuple, Optional

import config


def get_image_files(directory: str) -> List[str]:
    """
    获取指定目录下的所有图像文件
    
    Args:
        directory: 图像文件目录
        
    Returns:
        图像文件路径列表
    """
    if not os.path.exists(directory):
        return []
    
    image_files = []
    for filename in os.listdir(directory):
        file_path = os.path.join(directory, filename)
        if os.path.isfile(file_path):
            ext = os.path.splitext(filename)[1].lower()
            if ext in config.SUPPORTED_IMAGE_FORMATS:
                image_files.append(file_path)
    
    return sorted(image_files)

def get_corresponding_label_file(image_file: str, label_dir: str) -> Optional[str]:
    """
    获取与图像文件对应的标签文件
    
    Args:
        image_file: 图像文件的完整路径
        label_dir: 标签文件目录
        
    Returns:
        标签文件的完整路径，如果找不到则返回None
    """
    if not os.path.exists(label_dir):
        return None
    
    # 获取不带扩展名的文件名
    base_name = os.path.splitext(os.path.basename(image_file))[0]
    
    # 寻找对应的标签文件
    label_file_path = os.path.join(label_dir, f"{base_name}{config.LABEL_FILE_EXT}")
    
    return label_file_path if os.path.exists(label_file_path) else None

def read_label_file(label_file: str) -> List[List[float]]:
    """
    读取YOLO格式的标签文件
    
    Args:
        label_file: 标签文件的完整路径
        
    Returns:
        包含标签信息的列表，每个元素为 [class_id, center_x, center_y, width, height]
    """
    if not os.path.exists(label_file):
        print(f"【读取】标签文件不存在: {os.path.basename(label_file)}")
        return []
    
    labels = []
    try:
        with open(label_file, 'r') as f:
            lines = f.readlines()
            
            # 只打印文件名和行数，不打印详细内容
            print(f"【读取】标签文件: {os.path.basename(label_file)}, 行数: {len(lines)}")
            
            for i, line in enumerate(lines):
                parts = line.strip().split()
                if len(parts) == 5:
                    # 转换为 [class_id, center_x, center_y, width, height]
                    label = [float(parts[0]), float(parts[1]), float(parts[2]), 
                             float(parts[3]), float(parts[4])]
                    labels.append(label)
    except Exception as e:
        print(f"【读取】读取标签文件时出错: {e}")
        import traceback
        traceback.print_exc()
    
    # 只打印标签数量和类别ID
    if labels:
        class_ids = [int(label[0]) for label in labels if len(label) >= 1]
        print(f"【读取】共读取了 {len(labels)} 个标签，类别ID: {class_ids}")
    else:
        print(f"【读取】未读取到有效标签")
    
    return labels

def write_label_file(label_file: str, labels: List[List[float]]) -> bool:
    """
    将标签数据写入到文件
    
    Args:
        label_file: 标签文件路径
        labels: 标签数据列表
        
    Returns:
        是否成功写入文件
    """
    try:
        os.makedirs(os.path.dirname(label_file), exist_ok=True)
        with open(label_file, 'w') as f:
            for label in labels:
                if len(label) == 5:
                    # 格式化为YOLO格式: class_id center_x center_y width height
                    line = f"{int(label[0])} {label[1]} {label[2]} {label[3]} {label[4]}\n"
                    f.write(line)
        
        # 验证写入结果
        return os.path.exists(label_file)
    except Exception as e:
        print(f"写入标签文件时出错: {e}")
        return False

def move_files_to_target(image_file: str, label_file: str, target_dir: str, ship_type_id: int = None) -> Tuple[bool, str]:
    """
    将已标注的图像和标签文件移动到目标目录
    
    Args:
        image_file: 图像文件的完整路径
        label_file: 标签文件的完整路径（可能是临时文件）
        target_dir: 目标目录
        ship_type_id: 船舶类型ID，如果提供则按船舶类型分类保存
        
    Returns:
        (是否成功移动, 错误信息)
    """
    # 1. 检查源文件是否存在
    if not os.path.exists(image_file):
        return False, "源图像文件不存在"
    
    if not os.path.exists(label_file):
        return False, "源标签文件不存在"
    
    # 2. 获取源文件的基本信息
    image_basename = os.path.basename(image_file)
    base_name = os.path.splitext(image_basename)[0]
    
    try:
        # 3. 如果有船舶类型ID，获取对应的船舶类型名称并创建子目录
        if ship_type_id is not None:
            # 获取船舶类型名称
            ship_types = config.get_ship_types()
            ship_type_name = ship_types.get(str(ship_type_id), f"未知类型_{ship_type_id}")
            
            # 创建按船舶类型分类的子目录
            target_dir = os.path.join(target_dir, ship_type_name)
        
        # 4. 确保目标目录存在
        target_img_dir = os.path.join(target_dir, "images")
        target_label_dir = os.path.join(target_dir, "labels")
        os.makedirs(target_img_dir, exist_ok=True)
        os.makedirs(target_label_dir, exist_ok=True)
        
        # 5. 读取源标签文件内容
        source_labels = read_label_file(label_file)
        if not source_labels:
            return False, "标签文件为空或读取失败"
        
        # 6. 确定目标文件路径
        target_img_path = os.path.join(target_img_dir, image_basename)
        
        # 如果文件名中包含"temp"，说明是临时标签文件，需要生成正确的目标标签文件名
        if 'temp' in label_file and '.txt' in label_file:
            # 从图像文件名派生标签文件名，确保一致性
            target_label_path = os.path.join(target_label_dir, f"{base_name}{config.LABEL_FILE_EXT}")
        else:
            # 对于非临时标签文件，保留原始文件名
            target_label_path = os.path.join(target_label_dir, os.path.basename(label_file))
        
        # 7. 复制图像文件 - 使用copy2保留所有元数据
        try:
            shutil.copy2(image_file, target_img_path)
            
            # 验证复制是否成功
            if not os.path.exists(target_img_path):
                return False, "图像文件复制失败"
        except Exception as e:
            return False, f"复制图像文件失败: {e}"
        
        # 8. 处理标签文件
        try:
            if 'temp' in label_file and '.txt' in label_file:
                # 对于临时标签文件，直接写入目标目录中的新文件
                if not write_label_file(target_label_path, source_labels):
                    # 清理已复制的图像文件，避免不一致
                    try:
                        if os.path.exists(target_img_path):
                            os.unlink(target_img_path)
                    except Exception:
                        pass
                    return False, "写入目标标签文件失败"
            else:
                # 对于非临时标签文件，直接复制
                shutil.copy2(label_file, target_label_path)
            
            # 验证标签文件复制/写入结果
            if not os.path.exists(target_label_path):
                return False, "标签文件处理失败"
        except Exception as e:
            # 清理已复制的图像文件
            try:
                if os.path.exists(target_img_path):
                    os.unlink(target_img_path)
            except Exception:
                pass
            return False, f"处理标签文件失败: {e}"
        
        # 9. 验证目标标签文件内容
        target_labels = read_label_file(target_label_path)
        
        if not target_labels:
            return False, "目标标签文件验证失败"
        
        # 10. 验证标签数量
        if len(target_labels) != len(source_labels):
            return False, "目标标签文件内容验证失败"
        
        # 11. 逐一验证每个标签
        for i, (source_label, target_label) in enumerate(zip(source_labels, target_labels)):
            if int(target_label[0]) != int(source_label[0]):
                return False, f"标签 {i} 类别ID不一致: 源={int(source_label[0])}, 目标={int(target_label[0])}"
        
        return True, ""
    except Exception as e:
        return False, f"移动文件时出错: {e}"