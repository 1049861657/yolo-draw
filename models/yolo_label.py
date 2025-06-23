"""
YOLO标签处理模块
提供标签的解析、修改和保存功能
"""
from typing import List, Tuple

from utils import file_utils


class YoloLabel:
    """YOLO标签类，处理标签的加载、解析、修改和保存"""
    
    def __init__(self, image_path: str = None, label_path: str = None):
        """
        初始化YOLO标签对象
        
        Args:
            image_path: 图像文件路径
            label_path: 标签文件路径
        """
        self.image_path = image_path
        self.label_path = label_path
        self.labels = []  # 标签列表，格式为 [class_id, center_x, center_y, width, height]
        self.modified = False  # 标记是否已修改
        
        # 如果提供了标签文件路径，则加载标签
        if label_path and image_path:
            self.load_labels()
    
    def load_labels(self) -> bool:
        """
        从标签文件加载标签
        
        Returns:
            是否成功加载标签
        """
        if not self.label_path:
            return False
        
        labels = file_utils.read_label_file(self.label_path)
        if labels:
            self.labels = labels
            self.modified = False
            return True
        return False
    
    def save_labels(self) -> bool:
        """
        保存标签到标签文件
        
        Returns:
            是否成功保存标签
        """
        if not self.label_path:
            return False
        
        success = file_utils.write_label_file(self.label_path, self.labels)
        if success:
            self.modified = False
        return success
    
    def get_labels(self) -> List[List[float]]:
        """
        获取标签列表
        
        Returns:
            标签列表，每个元素为 [class_id, center_x, center_y, width, height]
        """
        return self.labels
    
    def update_label_class(self, index: int, new_class_id: int) -> bool:
        """
        更新指定索引标签的类别ID
        
        Args:
            index: 标签索引
            new_class_id: 新的类别ID
            
        Returns:
            是否成功更新
        """
        if 0 <= index < len(self.labels):
            self.labels[index][0] = float(new_class_id)
            self.modified = True
            return True
        return False
    
    def add_label(self, class_id: int, center_x: float, center_y: float, 
                 width: float, height: float) -> bool:
        """
        添加新标签
        
        Args:
            class_id: 类别ID
            center_x: 中心点x坐标（归一化）
            center_y: 中心点y坐标（归一化）
            width: 宽度（归一化）
            height: 高度（归一化）
            
        Returns:
            是否成功添加
        """
        self.labels.append([float(class_id), center_x, center_y, width, height])
        self.modified = True
        return True
    
    def remove_label(self, index: int) -> bool:
        """
        删除指定索引的标签
        
        Args:
            index: 标签索引
            
        Returns:
            是否成功删除
        """
        if 0 <= index < len(self.labels):
            self.labels.pop(index)
            self.modified = True
            return True
        return False
    
    def is_modified(self) -> bool:
        """
        检查标签是否已修改
        
        Returns:
            是否已修改
        """
        return self.modified
    
    def move_to_target(self, target_dir: str, ship_type_id: int = None) -> Tuple[bool, str]:
        """
        将图像和标签文件移动到目标目录
        
        Args:
            target_dir: 目标目录
            ship_type_id: 船舶类型ID，如果提供则按船舶类型分类保存
            
        Returns:
            (是否成功移动, 错误信息)
        """
        import tempfile
        import os
        
        if not self.image_path or not self.label_path:
            return False, "图像或标签文件路径未设置"
        
        # 1. 保存关键文件信息
        image_path = self.image_path
        label_path = self.label_path
        image_basename = os.path.basename(image_path)
        base_name = os.path.splitext(image_basename)[0]
        
        # 2. 检查文件是否存在
        if not os.path.exists(image_path):
            return False, f"图像文件不存在: {image_basename}"
            
        if not os.path.exists(label_path):
            return False, f"标签文件不存在: {os.path.basename(label_path)}"
        
        # 3. 创建临时目录
        try:
            temp_dir = os.path.join(tempfile.gettempdir(), "yolo_draw_temp")
            os.makedirs(temp_dir, exist_ok=True)
        except Exception as e:
            return False, f"创建临时目录失败: {e}"
            
        # 4. 创建与图像文件名相关联的临时标签文件
        temp_label_path = os.path.join(temp_dir, f"{base_name}_temp.txt")
        
        try:
            # 5. 确定是否需要使用临时文件
            if self.modified:
                # 将修改过的标签写入临时文件
                with open(temp_label_path, 'w') as temp_file:
                    for label in self.labels:
                        if len(label) == 5:
                            # 格式化为YOLO格式: class_id center_x center_y width height
                            line = f"{int(label[0])} {label[1]} {label[2]} {label[3]} {label[4]}\n"
                            temp_file.write(line)
                
                # 验证临时文件是否正确创建
                if os.path.exists(temp_label_path):
                    source_label_path = temp_label_path
                else:
                    return False, "临时标签文件创建失败"
            else:
                source_label_path = self.label_path
            
            # 6. 执行文件移动操作
            success, error_msg = file_utils.move_files_to_target(
                image_path,
                source_label_path, 
                target_dir,
                ship_type_id
            )
            
            # 7. 清理临时文件
            if self.modified and os.path.exists(temp_label_path):
                try:
                    os.unlink(temp_label_path)
                except Exception:
                    pass
            
            return success, error_msg
            
        except Exception as e:
            # 确保临时文件被删除
            try:
                if os.path.exists(temp_label_path):
                    os.unlink(temp_label_path)
            except Exception:
                pass
            
            return False, f"移动文件时出错: {e}"
    
    def update_label_coords(self, index: int, center_x: float, center_y: float, 
                    width: float, height: float) -> bool:
        """
        更新指定索引标签的坐标和尺寸
        
        Args:
            index: 标签索引
            center_x: 中心点x坐标（归一化，0-1）
            center_y: 中心点y坐标（归一化，0-1）
            width: 宽度（归一化，0-1）
            height: 高度（归一化，0-1）
            
        Returns:
            是否成功更新
        """
        if 0 <= index < len(self.labels):
            # 确保所有值都在0-1范围内
            center_x = max(0.0, min(1.0, center_x))
            center_y = max(0.0, min(1.0, center_y))
            width = max(0.001, min(1.0, width))  # 最小宽度为0.001
            height = max(0.001, min(1.0, height))  # 最小高度为0.001
            
            # 更新标签
            self.labels[index][1] = center_x
            self.labels[index][2] = center_y
            self.labels[index][3] = width
            self.labels[index][4] = height
            
            self.modified = True
            return True
        return False 