"""
YOLO船舶标注工具的主程序入口
"""
import sys
from PySide6.QtWidgets import QApplication

from ui.main_window_new import MainWindow

def main():
    """主函数"""
    # 创建Qt应用程序
    app = QApplication(sys.argv)
    
    # 创建主窗口对象
    window = MainWindow()
    
    # 运行应用
    window.run()
    
    # 执行应用程序
    sys.exit(app.exec())

if __name__ == "__main__":
    main() 