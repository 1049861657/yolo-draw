"""
编译Qt资源文件的脚本
"""
import os
import subprocess
from pathlib import Path

def main():
    """编译资源文件"""
    # 获取当前目录
    current_dir = Path(__file__).parent
    
    # 资源文件路径
    qrc_file = current_dir / "qt_resources.qrc"
    
    # 输出文件路径
    py_file = current_dir / "qt_resources_rc.py"
    
    # 检查资源文件是否存在
    if not qrc_file.exists():
        print(f"错误: 资源文件 {qrc_file} 不存在")
        return False
    
    # 编译命令
    cmd = ["pyside6-rcc", "-o", str(py_file), str(qrc_file)]
    
    try:
        # 执行编译
        subprocess.run(cmd, check=True)
        print(f"资源文件已编译: {py_file}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"编译资源文件时出错: {e}")
        return False
    except FileNotFoundError:
        print("错误: 没有找到pyside6-rcc工具，请确保PySide6已正确安装")
        return False

if __name__ == "__main__":
    main() 