"""
图像列表组件
负责图像文件的加载、分组和列表显示
"""
import os
import subprocess
from PySide6.QtCore import Qt, QObject, Signal, QUrl
from PySide6.QtWidgets import (
    QGroupBox, QVBoxLayout, QTreeWidget, QTreeWidgetItem, QMenu, QApplication
)
from PySide6.QtGui import QImage

from utils import file_utils
import config


class ImageListWidget(QGroupBox):
    """图像列表组件"""
    
    # 信号定义
    image_selected = Signal(str, int)  # 图像被选中信号 (文件路径, 索引)
    batch_selected = Signal(list)  # 批量选择信号 (文件路径列表)
    
    def __init__(self, parent=None):
        """初始化图像列表组件"""
        super().__init__("图像列表", parent)
        
        # 初始化状态变量
        self.image_files = []
        self.image_groups_by_id = {}
        self.current_group_id = None
        self.current_group_index = -1
        self.current_image_idx = -1  # 添加当前图像索引状态
        self.group_by_id = True
        self.is_review_mode = False
        self.labels_subdir = ""  # 添加标签目录路径
        self.show_label_count = False  # 是否显示标签数，默认关闭
        
        # 批量选择相关状态
        self.batch_selection_mode = False
        self.batch_selected_items = []  # 存储批量选择的项目
        self.batch_anchor_index = -1  # 批量选择的锚点索引
        
        # 创建UI
        self._init_ui()
        
        # 连接信号
        self._connect_signals()
    
    def _init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        
        # 创建树形控件
        self.image_treeview = QTreeWidget()
        self.image_treeview.setHeaderLabel("按ID分组的图像")
        
        # 添加右键菜单支持
        self.image_treeview.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        
        # 设置最小宽度
        self.image_treeview.setMinimumWidth(250)
        
        # 启用多选模式（仅在非分组模式下使用）
        self.image_treeview.setSelectionMode(QTreeWidget.SelectionMode.ExtendedSelection)
        
        layout.addWidget(self.image_treeview)
    
    def _connect_signals(self):
        """连接信号"""
        self.image_treeview.itemClicked.connect(self.on_tree_item_click)
        self.image_treeview.currentItemChanged.connect(self.on_tree_item_change)
        self.image_treeview.itemSelectionChanged.connect(self.on_selection_changed)
        self.image_treeview.customContextMenuRequested.connect(self.on_context_menu_requested)
    

    def get_label_stats(self, image_path):
        """获取图像对应的详细标签统计信息
        
        Args:
            image_path: 图像文件路径
            
        Returns:
            tuple: (标签总数, 标签类别ID列表, 平均面积占比)
        """
        if not self.labels_subdir:
            return 0, [], 0.0
            
        label_file = file_utils.get_corresponding_label_file(image_path, self.labels_subdir)
        if not label_file or not os.path.exists(label_file):
            return 0, [], 0.0
            
        labels = file_utils.read_label_file(label_file)
        if not labels:
            return 0, [], 0.0
        
        # 收集每个标签的类别ID和面积
        class_ids = []
        total_area = 0.0
        
        for label in labels:
            if len(label) == 5:
                class_id = int(label[0])
                width = float(label[3])
                height = float(label[4])
                
                # 收集类别ID
                class_ids.append(class_id)
                
                # 计算面积占比（YOLO格式中width和height都是归一化的）
                area = width * height
                total_area += area
        
        # 计算平均面积占比
        avg_area_percent = (total_area / len(labels) * 100) if labels else 0.0
        
        return len(labels), class_ids, avg_area_percent
    
    def load_images(self, images_subdir, labels_subdir=None):
        """加载图像文件
        
        Args:
            images_subdir: 图像子目录路径
            labels_subdir: 标签子目录路径（可选）
        """
        self.image_files = file_utils.get_image_files(images_subdir)
        
        # 保存标签目录路径，用于获取标签数量
        if labels_subdir:
            self.labels_subdir = labels_subdir
        else:
            # 尝试自动推断标签目录
            parent_dir = os.path.dirname(images_subdir)
            potential_labels_dir = os.path.join(parent_dir, "labels")
            if os.path.exists(potential_labels_dir):
                self.labels_subdir = potential_labels_dir
        
        if self.group_by_id:
            self.load_images_by_id()
        else:
            self.load_images_simple()
    
    def load_images_by_id(self):
        """按ID分组加载图像"""
        if not self.image_files:
            return
        
        # 解析每个图像的ID并分组
        self.image_groups_by_id = {}
        for img_file in self.image_files:
            img_id = self.parse_image_id(img_file)
            if img_id:
                if img_id not in self.image_groups_by_id:
                    self.image_groups_by_id[img_id] = []
                self.image_groups_by_id[img_id].append(img_file)
        
        # 对每个ID组内的图像按版本号排序
        for img_id, img_files in self.image_groups_by_id.items():
            img_files.sort(key=lambda x: self.extract_version_number(x))
        
        # 重新排序image_files以确保按照分组顺序显示
        self.image_files = []
        for img_files in self.image_groups_by_id.values():
            self.image_files.extend(img_files)
        
        # 更新显示
        self._update_tree_view()
        
        # 初始加载时展开第一个组（仅在有组的情况下）
        if self.image_groups_by_id and self.image_treeview.topLevelItemCount() > 0:
            first_item = self.image_treeview.topLevelItem(0)
            first_item.setExpanded(True)
    
    def load_images_simple(self):
        """简单加载图像（不分组）"""
        if not self.image_files:
            return
        
        # 清空分组数据
        self.image_groups_by_id = {}
        self.current_group_id = None
        
        # 按文件名排序
        self.image_files.sort()
        
        # 更新显示
        self._update_tree_view()
    
    def _update_tree_view(self):
        """更新树形控件显示"""
        self.image_treeview.clear()
        
        if not self.image_files:
            return
        
        if not self.group_by_id:
            # 简单模式：直接显示所有图像
            if self.batch_selection_mode:
                self._update_header_for_batch_mode()
            else:
                self.image_treeview.setHeaderLabel("图像列表")
            for img_file in self.image_files:
                item = QTreeWidgetItem()
                
                # 根据设置决定是否显示标签数量
                filename = os.path.basename(img_file)
                if self.show_label_count:
                    label_count, class_ids, avg_area = self.get_label_stats(img_file)
                    if label_count > 0:
                        # 显示每个标签的类别ID
                        class_stats = "|".join([str(class_id) for class_id in class_ids])
                        display_text = f"{filename} - {class_stats} [{avg_area:.1f}%]"
                    else:
                        display_text = f"{filename}"
                else:
                    display_text = filename
                
                item.setText(0, display_text)
                item.setData(0, Qt.ItemDataRole.UserRole, img_file)
                self.image_treeview.addTopLevelItem(item)
        else:
            # 分组模式：按ID分组显示
            self.image_treeview.setHeaderLabel("按ID分组的图像")
            
            # 按ID排序显示
            for group_id in sorted(self.image_groups_by_id.keys()):
                group_files = self.image_groups_by_id[group_id]
                
                # 创建组节点（不显示标签数量）
                group_item = QTreeWidgetItem()
                group_item.setText(0, f"{group_id}: ({len(group_files)} 个文件)")
                
                # 添加组内的图像文件
                for img_file in group_files:
                    child_item = QTreeWidgetItem()
                    
                    # 根据设置决定是否显示标签数量
                    filename = os.path.basename(img_file)
                    if self.show_label_count:
                        label_count, class_ids, avg_area = self.get_label_stats(img_file)
                        if label_count > 0:
                            # 显示每个标签的类别ID
                            class_stats = "|".join([str(class_id) for class_id in class_ids])
                            display_text = f"{filename} - {class_stats} [{avg_area:.1f}%]"
                        else:
                            display_text = f"{filename}"
                    else:
                        display_text = filename
                    
                    child_item.setText(0, display_text)
                    child_item.setData(0, Qt.ItemDataRole.UserRole, img_file)
                    group_item.addChild(child_item)
                
                self.image_treeview.addTopLevelItem(group_item)
    
    def on_tree_item_click(self, item, column):
        """处理树形控件项目点击事件"""
        if not self.group_by_id:
            # 简单模式：直接处理图像文件
            file_path = item.data(0, Qt.ItemDataRole.UserRole)
            if file_path:
                # 查找文件在列表中的索引并更新状态
                for idx, img_file in enumerate(self.image_files):
                    if img_file == file_path:
                        self.current_image_idx = idx
                        self.image_selected.emit(file_path, idx)
                        return
            return
        
        # 分组模式：原有逻辑
        if item.parent() is None:
            # 如果是根节点，则展开或折叠
            item.setExpanded(not item.isExpanded())
            return
        
        # 获取所属的ID组
        group_id = item.parent().text(0).split(':')[0].strip()
        self.current_group_id = group_id
        
        # 更新当前组在所有组中的索引位置
        all_group_ids = sorted(list(self.image_groups_by_id.keys()))
        if group_id in all_group_ids:
            self.current_group_index = all_group_ids.index(group_id)
        
        # 获取点击的文件路径（直接从UserRole获取）
        file_path = item.data(0, Qt.ItemDataRole.UserRole)
        if file_path:
            for idx, img_file in enumerate(self.image_files):
                if img_file == file_path:
                    self.current_image_idx = idx
                    self.image_selected.emit(img_file, idx)
                    break
    
    def on_tree_item_change(self, current, previous):
        """处理树形控件项目选择变化事件"""
        if not current:
            return
            
        if not self.group_by_id:
            # 简单模式
            file_path = current.data(0, Qt.ItemDataRole.UserRole)
            if file_path:
                for idx, img_file in enumerate(self.image_files):
                    if img_file == file_path:
                        self.current_image_idx = idx
                        self.image_selected.emit(img_file, idx)
                        return
            return
        
        # 分组模式
        if current.parent() is None:
            return
        
        # 获取所属的ID组
        group_id = current.parent().text(0).split(':')[0].strip()
        self.current_group_id = group_id
        
        # 更新当前组在所有组中的索引位置
        all_group_ids = sorted(list(self.image_groups_by_id.keys()))
        if group_id in all_group_ids:
            self.current_group_index = all_group_ids.index(group_id)
        
        # 获取选择的文件路径（直接从UserRole获取）
        file_path = current.data(0, Qt.ItemDataRole.UserRole)
        if file_path:
            for idx, img_file in enumerate(self.image_files):
                if img_file == file_path:
                    self.current_image_idx = idx
                    self.image_selected.emit(img_file, idx)
                    break
    
    def parse_image_id(self, image_path):
        """从图像文件名解析ID"""
        try:
            filename = os.path.basename(image_path)
            if '_v' in filename:
                return filename.split('_v')[0]
        except Exception as e:
            print(f"解析图像ID时出错: {e}")
        return None
    
    def extract_version_number(self, image_path):
        """从图像文件名提取版本号"""
        try:
            filename = os.path.basename(image_path)
            if '_v' in filename:
                version_str = filename.split('_v')[1].split(".")[0]
                return int(version_str)
        except Exception as e:
            print(f"提取版本号时出错: {e}")
        return -1
    
    def set_group_by_id(self, group_by_id):
        """设置是否按ID分组"""
        self.group_by_id = group_by_id
        if self.image_files:
            if self.group_by_id:
                self.load_images_by_id()
            else:
                self.load_images_simple()
    
    def set_review_mode(self, is_review_mode):
        """设置审核模式"""
        self.is_review_mode = is_review_mode
        self._update_tree_view()
    
    def set_show_label_count(self, show_label_count):
        """设置是否显示标签数"""
        self.show_label_count = show_label_count
        # 如果当前已有图像数据，重新更新显示
        if self.image_files:
            self._update_tree_view()
    
    def select_tree_item_by_path(self, img_path):
        """根据图像路径在树形控件中选中对应的项目"""
        img_name = os.path.basename(img_path)
        
        if not self.group_by_id:
            # 简单模式：通过UserRole数据查找
            for i in range(self.image_treeview.topLevelItemCount()):
                item = self.image_treeview.topLevelItem(i)
                item_path = item.data(0, Qt.ItemDataRole.UserRole)
                if item_path == img_path:
                    self.image_treeview.setCurrentItem(item)
                    # 更新当前图像索引
                    for idx, img_file in enumerate(self.image_files):
                        if img_file == img_path:
                            self.current_image_idx = idx
                            break
                    return True
        else:
            # 分组模式：查找对应的组和子项
            img_id = self.parse_image_id(img_path)
            for i in range(self.image_treeview.topLevelItemCount()):
                root_item = self.image_treeview.topLevelItem(i)
                root_text = root_item.text(0)
                
                if root_text.startswith(f"{img_id}:"):
                    for j in range(root_item.childCount()):
                        child_item = root_item.child(j)
                        child_path = child_item.data(0, Qt.ItemDataRole.UserRole)
                        if child_path == img_path:
                            root_item.setExpanded(True)
                            self.image_treeview.setCurrentItem(child_item)
                            # 更新状态
                            self.current_group_id = img_id
                            all_group_ids = sorted(list(self.image_groups_by_id.keys()))
                            if img_id in all_group_ids:
                                self.current_group_index = all_group_ids.index(img_id)
                            for idx, img_file in enumerate(self.image_files):
                                if img_file == img_path:
                                    self.current_image_idx = idx
                                    break
                            return True
        
        return False
    
    def navigate_up(self):
        """向上导航（W键功能）"""
        current_item = self.image_treeview.currentItem()
        if not current_item:
            # 如果没有选中项，选择第一个可见项
            if self.image_treeview.topLevelItemCount() > 0:
                if self.group_by_id:
                    # 分组模式：选择第一个组的第一个子项
                    root_item = self.image_treeview.topLevelItem(0)
                    if root_item.childCount() > 0:
                        root_item.setExpanded(True)
                        self.image_treeview.setCurrentItem(root_item.child(0))
                else:
                    # 简单模式：选择第一个项
                    self.image_treeview.setCurrentItem(self.image_treeview.topLevelItem(0))
            return
        
        if not self.group_by_id:
            # 简单模式：选择上一个项
            current_index = self.image_treeview.indexOfTopLevelItem(current_item)
            if current_index > 0:
                self.image_treeview.setCurrentItem(self.image_treeview.topLevelItem(current_index - 1))
            return
        
        # 分组模式：原有逻辑
        parent_item = current_item.parent()
        
        # 如果当前是根节点，无法向上移动
        if not parent_item:
            return
        
        # 获取当前项在父节点中的索引
        index = parent_item.indexOfChild(current_item)
        
        # 向上移动（如果可能）
        if index > 0:
            # 选择同一组中的上一个项
            parent_item.setExpanded(True)
            self.image_treeview.setCurrentItem(parent_item.child(index - 1))
        else:
            # 已经是该组的第一项，尝试移动到上一个组的最后一项
            parent_index = self.image_treeview.indexOfTopLevelItem(parent_item)
            if parent_index > 0:
                prev_parent = self.image_treeview.topLevelItem(parent_index - 1)
                if prev_parent.childCount() > 0:
                    prev_parent.setExpanded(True)
                    # 选择上一个组的最后一个项
                    self.image_treeview.setCurrentItem(prev_parent.child(prev_parent.childCount() - 1))
    
    def navigate_down(self):
        """向下导航（S键功能）"""
        current_item = self.image_treeview.currentItem()
        if not current_item:
            # 如果没有选中项，选择第一个可见项
            if self.image_treeview.topLevelItemCount() > 0:
                if self.group_by_id:
                    # 分组模式：选择第一个组的第一个子项
                    root_item = self.image_treeview.topLevelItem(0)
                    if root_item.childCount() > 0:
                        root_item.setExpanded(True)
                        self.image_treeview.setCurrentItem(root_item.child(0))
                else:
                    # 简单模式：选择第一个项
                    self.image_treeview.setCurrentItem(self.image_treeview.topLevelItem(0))
            return
        
        if not self.group_by_id:
            # 简单模式：选择下一个项
            current_index = self.image_treeview.indexOfTopLevelItem(current_item)
            if current_index < self.image_treeview.topLevelItemCount() - 1:
                self.image_treeview.setCurrentItem(self.image_treeview.topLevelItem(current_index + 1))
            return
        
        # 分组模式：原有逻辑
        parent_item = current_item.parent()
        
        # 如果当前是根节点，无法向下移动
        if not parent_item:
            return
        
        # 获取当前项在父节点中的索引
        index = parent_item.indexOfChild(current_item)
        
        # 向下移动（如果可能）
        if index < parent_item.childCount() - 1:
            # 选择同一组中的下一个项
            parent_item.setExpanded(True)
            self.image_treeview.setCurrentItem(parent_item.child(index + 1))
        else:
            # 已经是该组的最后一项，尝试移动到下一个组的第一项
            parent_index = self.image_treeview.indexOfTopLevelItem(parent_item)
            if parent_index < self.image_treeview.topLevelItemCount() - 1:
                next_parent = self.image_treeview.topLevelItem(parent_index + 1)
                if next_parent.childCount() > 0:
                    next_parent.setExpanded(True)
                    # 选择下一个组的第一个项
                    self.image_treeview.setCurrentItem(next_parent.child(0))
    
    def select_next_image_after_removal(self, removed_img_path, current_in_group_idx=-1):
        """移除图像后选择下一张图像（迁移自重构前代码）"""
        selected_next = False
        
        if not self.group_by_id:
            # 简单模式：选择下一张图像
            if self.image_files:
                # 确保当前索引不超出范围
                if self.current_image_idx >= len(self.image_files):
                    self.current_image_idx = len(self.image_files) - 1
                
                # 如果还有图像，选择当前索引位置的图像
                if self.current_image_idx >= 0 and self.current_image_idx < len(self.image_files):
                    next_img_path = self.image_files[self.current_image_idx]
                    if self.select_tree_item_by_path(next_img_path):
                        self.image_selected.emit(next_img_path, self.current_image_idx)
                        selected_next = True
            return selected_next
        
        # 分组模式：如果当前组还存在且有图像
        if self.current_group_id and self.current_group_id in self.image_groups_by_id:
            remaining_images = self.image_groups_by_id[self.current_group_id]
            
            if remaining_images and current_in_group_idx >= 0:
                # 尝试选择当前组内的下一张图片
                next_idx_in_group = min(current_in_group_idx, len(remaining_images) - 1)
                next_image_path = remaining_images[next_idx_in_group]
                
                # 找到该图像在列表中的索引
                for idx, img_path in enumerate(self.image_files):
                    if img_path == next_image_path:
                        # 选中该图像
                        if self.select_tree_item_by_path(img_path):
                            self.image_selected.emit(img_path, idx)
                            selected_next = True
                            break
        
        # 如果还没有选择下一张，选择下一个组的第一张
        if not selected_next:
            selected_next = self.select_next_group_first_image()
        
        return selected_next
    
    def select_next_group_first_image(self):
        """选择下一个ID组的第一张图片（迁移自重构前代码）"""
        # 获取所有ID组的列表并排序
        all_group_ids = sorted(list(self.image_groups_by_id.keys()))
        
        if not all_group_ids:
            # 没有更多的分组
            self.current_group_id = None
            self.current_group_index = -1
            self.current_image_idx = -1
            self.image_treeview.clear()
            return False
        
        # 选择下一个组
        next_idx = 0
        if self.current_group_index >= 0:
            # 如果当前组索引有效，选择相同索引位置的组（删除后的下一组）
            if self.current_group_index < len(all_group_ids):
                next_idx = self.current_group_index
            else:
                # 如果索引超出范围，选择最后一个组
                next_idx = len(all_group_ids) - 1
        
        # 获取下一个组ID
        next_group_id = all_group_ids[next_idx]
        
        # 获取下一个组的第一张图片
        if next_group_id in self.image_groups_by_id and self.image_groups_by_id[next_group_id]:
            next_image_path = self.image_groups_by_id[next_group_id][0]
            
            # 找到该图像在列表中的索引
            for idx, img_path in enumerate(self.image_files):
                if img_path == next_image_path:
                    # 找到树形控件中对应的项目并选中
                    if self.select_tree_item_by_path(img_path):
                        # 更新状态
                        self.current_image_idx = idx
                        self.current_group_id = next_group_id
                        self.current_group_index = next_idx
                        # 发送信号
                        self.image_selected.emit(img_path, idx)
                        return True
        
        return False
    
    def remove_current_image(self):
        """从列表中移除当前图像并自动选择下一张"""
        # 获取当前选中的项目
        current_item = self.image_treeview.currentItem()
        if not current_item:
            return
            
        current_img_path = None
        current_in_group_idx = -1
        
        if not self.group_by_id:
            # 简单模式：直接获取文件路径
            current_img_path = current_item.data(0, Qt.ItemDataRole.UserRole)
        else:
            # 分组模式：从子项直接获取文件路径
            if current_item.parent() is None:
                return  # 如果是根节点，无法移除
                
            # 直接从UserRole获取文件路径
            current_img_path = current_item.data(0, Qt.ItemDataRole.UserRole)
            
            # 获取当前图像在组内的索引
            if self.current_group_id and self.current_group_id in self.image_groups_by_id:
                group_images = self.image_groups_by_id[self.current_group_id]
                if current_img_path in group_images:
                    current_in_group_idx = group_images.index(current_img_path)
        
        if not current_img_path:
            return
        
        # 在简单模式下，记录当前图像在列表中的索引
        removed_img_idx = -1
        if not self.group_by_id and current_img_path in self.image_files:
            removed_img_idx = self.image_files.index(current_img_path)
            
        # 从图像文件列表中移除
        if current_img_path in self.image_files:
            self.image_files.remove(current_img_path)
        
        # 在简单模式下，更新当前图像索引
        if not self.group_by_id and removed_img_idx >= 0:
            # 如果移除的不是最后一张图像，保持当前索引
            # 如果移除的是最后一张图像，索引减1
            if removed_img_idx >= len(self.image_files):
                self.current_image_idx = len(self.image_files) - 1
            else:
                self.current_image_idx = removed_img_idx
        
        # 如果是分组模式，也要从分组中移除
        if self.group_by_id and self.current_group_id:
            if self.current_group_id in self.image_groups_by_id:
                group_files = self.image_groups_by_id[self.current_group_id]
                if current_img_path in group_files:
                    group_files.remove(current_img_path)
                    
                    # 如果组变空了，删除整个组
                    if not group_files:
                        del self.image_groups_by_id[self.current_group_id]
                        self.current_group_id = None
        
        # 重新加载图像列表
        self._update_tree_view()
        
        # 自动选择下一张图像
        self.select_next_image_after_removal(current_img_path, current_in_group_idx)
    
    def remove_current_group(self):
        """从列表中移除当前组并自动选择下一个组"""
        if not self.group_by_id or not self.current_group_id:
            return
            
        # 在移除之前，预先计算下一个组的信息
        all_group_ids = sorted(list(self.image_groups_by_id.keys()))
        next_group_id = None
        next_group_index = -1
        
        if self.current_group_id in all_group_ids:
            current_idx = all_group_ids.index(self.current_group_id)
            
            # 计算下一个组的索引
            if current_idx < len(all_group_ids) - 1:
                # 选择下一个组
                next_group_index = current_idx
                next_group_id = all_group_ids[current_idx + 1]
            elif len(all_group_ids) > 1:
                # 如果是最后一个组，选择第一个组
                next_group_index = 0
                next_group_id = all_group_ids[0]
            # 如果只有一个组，next_group_id保持None
        
        # 获取当前组的所有图像
        if self.current_group_id in self.image_groups_by_id:
            group_files = self.image_groups_by_id[self.current_group_id]
            
            # 从主图像列表中移除所有组内图像
            for img_file in group_files:
                if img_file in self.image_files:
                    self.image_files.remove(img_file)
            
            # 删除组
            del self.image_groups_by_id[self.current_group_id]
        
        # 重置当前组
        self.current_group_id = None
        self.current_group_index = -1
        
        # 重新加载图像列表
        self._update_tree_view()
        
        # 如果有下一个组，选择它的第一张图片
        if next_group_id and next_group_id in self.image_groups_by_id:
            group_images = self.image_groups_by_id[next_group_id]
            if group_images:
                next_image_path = group_images[0]
                
                # 找到该图像在列表中的索引
                for idx, img_path in enumerate(self.image_files):
                    if img_path == next_image_path:
                        # 选中该图像
                        if self.select_tree_item_by_path(img_path):
                            # 更新状态
                            self.current_image_idx = idx
                            self.current_group_id = next_group_id
                            self.current_group_index = next_group_index
                            # 发送信号
                            self.image_selected.emit(img_path, idx)
                            break
    
    def select_next_image(self):
        """选择下一个图像（重写以支持两种模式）"""
        if not self.image_files:
            return
            
        if self.group_by_id:
            # 分组模式下选择下一个组的第一个图像
            self.select_next_group_first_image()
        else:
            # 简单模式下选择下一个图像
            if self.current_image_idx >= 0 and self.current_image_idx < len(self.image_files) - 1:
                next_idx = self.current_image_idx + 1
            else:
                next_idx = 0  # 循环到第一个
            
            if next_idx < len(self.image_files):
                next_img_path = self.image_files[next_idx]
                if self.select_tree_item_by_path(next_img_path):
                    self.current_image_idx = next_idx
                    self.image_selected.emit(next_img_path, next_idx)
    
    def on_selection_changed(self):
        """处理选择变化事件（用于批量选择）"""
        if self.group_by_id:
            # 分组模式下不支持批量选择
            return
            
        selected_items = self.image_treeview.selectedItems()
        
        if len(selected_items) > 1:
            # 进入批量选择模式
            if not self.batch_selection_mode:
                self.batch_selection_mode = True
                self._update_header_for_batch_mode()
            
            # 收集选中的文件路径
            selected_paths = []
            for item in selected_items:
                file_path = item.data(0, Qt.ItemDataRole.UserRole)
                if file_path:
                    selected_paths.append(file_path)
            
            self.batch_selected_items = selected_paths
            self.batch_selected.emit(selected_paths)
        else:
            # 退出批量选择模式
            if self.batch_selection_mode:
                self.batch_selection_mode = False
                self.batch_selected_items = []
                self._update_header_for_normal_mode()
                
                # 如果只有一个选中项，发送单选信号
                if len(selected_items) == 1:
                    item = selected_items[0]
                    file_path = item.data(0, Qt.ItemDataRole.UserRole)
                    if file_path:
                        for idx, img_file in enumerate(self.image_files):
                            if img_file == file_path:
                                self.current_image_idx = idx
                                self.image_selected.emit(file_path, idx)
                                break
    
    def _update_header_for_batch_mode(self):
        """更新标题为批量选择模式"""
        count = len(self.batch_selected_items)
        self.image_treeview.setHeaderLabel(f"图像列表 - 已选择 {count} 项")
    
    def _update_header_for_normal_mode(self):
        """更新标题为正常模式"""
        if self.group_by_id:
            self.image_treeview.setHeaderLabel("按ID分组的图像")
        else:
            self.image_treeview.setHeaderLabel("图像列表")
    
    def clear_batch_selection(self):
        """清空批量选择"""
        self.batch_selection_mode = False
        self.batch_selected_items = []
        self.batch_anchor_index = -1
        self.image_treeview.clearSelection()
        self._update_header_for_normal_mode()
    
    def get_batch_selected_items(self):
        """获取批量选择的项目"""
        return self.batch_selected_items.copy()
    
    def is_in_batch_mode(self):
        """检查是否处于批量选择模式"""
        return self.batch_selection_mode
    
    def remove_batch_selected_images(self):
        """移除批量选择的图像"""
        if not self.batch_selection_mode or not self.batch_selected_items:
            return
        
        # 从图像列表中移除选中的图像
        for img_path in self.batch_selected_items:
            if img_path in self.image_files:
                self.image_files.remove(img_path)
        
        # 清空批量选择状态
        self.clear_batch_selection()
        
        # 刷新显示
        self._update_tree_view()
    
    def update_image_item_text(self, image_path):
        """更新特定图像项的文本显示（仅更新标签数）
        
        Args:
            image_path: 要更新的图像文件路径
        """
        if not image_path:
            return
        
        # 根据设置决定显示格式
        filename = os.path.basename(image_path)
        if self.show_label_count:
            # 获取新的标签统计信息
            label_count, class_ids, avg_area = self.get_label_stats(image_path)
            if label_count > 0:
                # 显示每个标签的类别ID
                class_stats = "|".join([str(class_id) for class_id in class_ids])
                new_display_text = f"{filename} - {class_stats} [{avg_area:.1f}%]"
            else:
                new_display_text = f"{filename}"
        else:
            new_display_text = filename
        
        # 查找并更新对应的树形控件项
        if not self.group_by_id:
            # 简单模式：直接在顶级项中查找
            for i in range(self.image_treeview.topLevelItemCount()):
                item = self.image_treeview.topLevelItem(i)
                item_path = item.data(0, Qt.ItemDataRole.UserRole)
                if item_path == image_path:
                    item.setText(0, new_display_text)
                    break
        else:
            # 分组模式：在组的子项中查找
            for i in range(self.image_treeview.topLevelItemCount()):
                group_item = self.image_treeview.topLevelItem(i)
                for j in range(group_item.childCount()):
                    child_item = group_item.child(j)
                    child_path = child_item.data(0, Qt.ItemDataRole.UserRole)
                    if child_path == image_path:
                        child_item.setText(0, new_display_text)
                        return
    
    def on_context_menu_requested(self, position):
        """处理右键菜单请求"""
        # 获取右键点击的项目
        item = self.image_treeview.itemAt(position)
        if not item:
            return
        
        # 获取文件路径
        file_path = item.data(0, Qt.ItemDataRole.UserRole)
        if not file_path:
            # 如果是分组节点，不显示菜单
            return
        
        # 创建右键菜单
        context_menu = QMenu(self)
        
        # 添加"打开所在文件夹"选项
        open_folder_action = context_menu.addAction("📁 打开所在文件夹")
        open_folder_action.triggered.connect(lambda: self.open_file_folder(file_path))
        
        # 添加"复制图片"选项
        copy_image_action = context_menu.addAction("📋 复制图片")
        copy_image_action.triggered.connect(lambda: self.copy_image_to_clipboard(file_path))
        
        # 显示菜单
        context_menu.exec(self.image_treeview.viewport().mapToGlobal(position))
    
    def open_file_folder(self, file_path):
        """打开文件所在的文件夹并选中文件"""
        if not os.path.exists(file_path):
            return
        
        try:
            # Windows: 使用explorer /select命令，需要规范化路径
            normalized_path = os.path.normpath(file_path)
            # 不使用check=True，因为explorer即使成功也可能返回非零状态码
            subprocess.run(['explorer', '/select,', normalized_path], capture_output=True)
            print(f"已打开文件夹并选中: {os.path.basename(file_path)}")
        except Exception as e:
            print(f"打开文件夹失败: {e}")
    
    def copy_image_to_clipboard(self, file_path):
        """复制图片文件到剪贴板"""
        if not os.path.exists(file_path):
            print(f"文件不存在: {file_path}")
            return
        
        try:
            # 使用Qt的剪贴板功能复制图片数据
            clipboard = QApplication.clipboard()
            
            # 加载图片
            image = QImage(file_path)
            if image.isNull():
                print(f"无法加载图片: {file_path}")
                return
            
            # 将图片复制到剪贴板
            clipboard.setImage(image)
            print(f"已复制图片到剪贴板: {os.path.basename(file_path)}")
            
        except Exception as e:
            print(f"复制图片失败: {e}")
    
    def get_current_and_previous_images(self):
        """获取当前选中项及之前的所有图片路径（仅在直接加载模式下）
        
        Returns:
            list: 包含当前选中项及之前所有图片路径的列表，如果不在直接加载模式或没有选中项则返回空列表
        """
        # 只在直接加载模式下工作
        if self.group_by_id:
            return []
        
        # 检查是否有当前选中的图片
        if self.current_image_idx < 0 or self.current_image_idx >= len(self.image_files):
            return []
        
        # 返回从第一张到当前选中项（包含）的所有图片路径
        return self.image_files[:self.current_image_idx + 1]