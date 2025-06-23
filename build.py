"""
YOLO船舶标注工具打包脚本
支持在uv环境或pip环境下运行
"""
import os
import sys
import shutil
import subprocess
import platform
import importlib.util

# 导入配置模块
import config

def check_environment():
    """检查运行环境，确定是使用uv还是pip"""
    print("正在检查Python环境...")
    
    # 检查是否存在uv环境
    is_uv_env = False
    
    # 检查uv命令是否可用
    try:
        result = subprocess.run(['uv', '--version'], 
                           capture_output=True, 
                           text=True,
                           check=False)
        if result.returncode == 0:
            is_uv_env = True
            print(f"检测到uv环境: {result.stdout.strip()}")
    except FileNotFoundError:
        pass
    
    # 检查是否存在uv.lock文件
    if os.path.exists('uv.lock'):
        is_uv_env = True
        print("检测到uv.lock文件")
    
    print(f"当前使用环境: {'uv' if is_uv_env else 'pip'}")
    return is_uv_env

def check_pyinstaller():
    """检查PyInstaller是否已安装"""
    print("正在检查PyInstaller...")
    
    if importlib.util.find_spec("PyInstaller") is None:
        print("未安装PyInstaller，请先安装")
        print("可使用以下命令安装: pip install pyinstaller 或 uv pip install pyinstaller")
        return False
        
    print("PyInstaller已安装")
    return True

def clean_build_folders():
    """清理旧的构建文件夹"""
    folders = ['build', 'dist']
    for folder in folders:
        if os.path.exists(folder):
            print(f"清理文件夹: {folder}")
            shutil.rmtree(folder)

def build_app():
    """构建应用程序"""
    print("开始构建应用程序...")
    
    # 应用信息
    app_name = config.APP_NAME
    
    # 项目路径
    project_path = os.path.abspath(os.path.dirname(__file__))
    
    # 主脚本路径
    main_script = os.path.join(project_path, 'main.py')
    
    # 图标路径
    icon_path = os.path.join(project_path, 'resources', 'icon.ico')
    icon_arg = ['--icon', icon_path] if os.path.exists(icon_path) else []
    
    # 构建PyInstaller命令 - 不再包含--add-data参数，避免resources被放入_internal
    pyinstaller_cmd = [
        'pyinstaller',
        '--name', app_name,
        '--clean',
        '--onedir',
        '--noconfirm',
        '--windowed',  # 无控制台窗口
        *icon_arg,
        main_script
    ]
    
    print(f"执行命令: {' '.join(pyinstaller_cmd)}")
    
    # 执行PyInstaller命令
    result = subprocess.run(
        pyinstaller_cmd, 
        capture_output=True, 
        text=True
    )
    
    # 输出构建日志
    if result.returncode != 0:
        print("构建失败，错误信息:")
        print(result.stderr)
        return False
    
    print("应用程序构建成功!")
    return True

def copy_resources():
    """复制资源文件到dist目录"""
    dist_dir = os.path.join('dist', config.APP_NAME)
    src_resources = 'resources'
    dst_resources = os.path.join(dist_dir, 'resources')
    
    print("正在复制资源文件...")
    if os.path.exists(src_resources):
        if os.path.exists(dst_resources):
            shutil.rmtree(dst_resources)
        shutil.copytree(src_resources, dst_resources)
        print("resources目录已复制到应用根目录")
    else:
        print("错误: 未找到resources目录")
        return False
    
    # 复制README.md文件（如果存在）
    readme_file = 'README.md'
    if os.path.exists(readme_file):
        shutil.copy2(readme_file, os.path.join(dist_dir, readme_file))
        print(f"{readme_file}已复制")
    
    return True

def prepare_output():
    """准备输出文件夹和打包分发版本"""
    # 创建输出目录
    output_dir = 'output'
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # 打包分发版本
    print("正在创建分发压缩包...")
    archive_name = os.path.join(output_dir, f'{config.APP_NAME}_v{config.APP_VERSION}')
    
    try:
        shutil.make_archive(archive_name, 'zip', 'dist', config.APP_NAME)
        print(f"分发版本已创建: {archive_name}.zip")
        return True
    except Exception as e:
        print(f"创建分发版本时出错: {e}")
        return False

def verify_build():
    """验证构建结果"""
    print("正在验证构建结果...")
    
    dist_dir = os.path.join('dist', config.APP_NAME)
    
    # 检查主程序是否存在
    if platform.system() == 'Windows':
        main_exe = os.path.join(dist_dir, f"{config.APP_NAME}.exe")
    else:
        main_exe = os.path.join(dist_dir, config.APP_NAME)
    
    if not os.path.exists(main_exe):
        print(f"错误: 未找到主程序 {main_exe}")
        return False
    
    print("构建验证通过!")
    return True

def main():
    """主函数"""
    print(f"=== 开始打包 {config.APP_NAME} v{config.APP_VERSION} ===")
    
    # 检查环境
    check_environment()
    
    # 检查PyInstaller
    if not check_pyinstaller():
        sys.exit(1)
    
    # 清理旧的构建文件夹
    clean_build_folders()
    
    # 构建应用
    if not build_app():
        print("错误: 构建应用失败")
        sys.exit(1)
    
    # 复制资源文件（现在直接复制到dist目录，而不放在_internal中）
    if not copy_resources():
        print("警告: 资源文件复制失败")
    
    # 验证构建结果
    if not verify_build():
        print("错误: 构建验证失败")
        sys.exit(1)
    
    # 准备输出
    if not prepare_output():
        print("警告: 分发压缩包创建失败")
        sys.exit(1)
    
    print(f"=== {config.APP_NAME} v{config.APP_VERSION} 打包成功! ===")

if __name__ == "__main__":
    main() 