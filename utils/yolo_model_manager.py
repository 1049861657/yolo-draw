"""
YOLO模型管理器
处理YOLO模型的加载、选择和配置保存
"""
import os
import json
import config


class YoloModelManager:
    """YOLO模型管理器类"""
    
    def __init__(self):
        """初始化模型管理器"""
        self.settings_file = config.SETTINGS_FILE
        self.models_dir = config.YOLO_MODELS_DIR
        self.default_model = config.DEFAULT_YOLO_MODEL
    
    def get_available_models(self):
        """获取可用的YOLO模型列表"""
        models = []
        if os.path.exists(self.models_dir):
            for file in os.listdir(self.models_dir):
                if file.endswith('.pt'):
                    models.append(file)
        return sorted(models)
    
    def load_user_settings(self):
        """加载用户设置"""
        settings = {
            'selected_yolo_model': self.default_model
        }
        
        if os.path.exists(self.settings_file):
            try:
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    user_settings = json.load(f)
                    settings.update(user_settings)
            except Exception as e:
                print(f"加载用户设置失败: {e}")
        
        return settings
    
    def save_user_settings(self, settings):
        """保存用户设置"""
        try:
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(settings, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"保存用户设置失败: {e}")
            return False
    
    def get_selected_model(self):
        """获取用户选择的YOLO模型"""
        settings = self.load_user_settings()
        selected_model = settings.get('selected_yolo_model', self.default_model)
        
        # 检查选择的模型是否存在
        model_path = os.path.join(self.models_dir, selected_model)
        if not os.path.exists(model_path):
            # 如果选择的模型不存在，返回第一个可用的模型
            available_models = self.get_available_models()
            if available_models:
                selected_model = available_models[0]
                # 更新设置
                settings['selected_yolo_model'] = selected_model
                self.save_user_settings(settings)
            else:
                selected_model = self.default_model
        
        return selected_model
    
    def set_selected_model(self, model_name):
        """设置用户选择的YOLO模型"""
        settings = self.load_user_settings()
        settings['selected_yolo_model'] = model_name
        return self.save_user_settings(settings)
    
    def get_model_path(self, model_name=None):
        """获取模型文件路径"""
        if model_name is None:
            model_name = self.get_selected_model()
        
        return os.path.join(self.models_dir, model_name)
    
    def model_exists(self, model_name):
        """检查模型文件是否存在"""
        model_path = self.get_model_path(model_name)
        return os.path.exists(model_path)
    
    def get_model_info(self, model_name):
        """获取模型信息"""
        model_path = self.get_model_path(model_name)
        
        if not os.path.exists(model_path):
            return None
        
        # 获取文件大小
        file_size = os.path.getsize(model_path)
        size_mb = file_size / (1024 * 1024)
        
        return {
            'name': model_name,
            'path': model_path,
            'size_mb': size_mb,
            'exists': True
        } 