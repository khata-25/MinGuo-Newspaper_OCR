"""
打包脚本 - 创建可分发的应用程序包
Packaging Script - Create distributable application package

使用方法:
1. 安装 PyInstaller: pip install pyinstaller
2. 运行此脚本: python package_app.py

生成的可执行文件将在 dist/ 目录中
"""
import os
import sys
import shutil
from pathlib import Path
import subprocess

def main():
    print("=" * 60)
    print("民国报纸 OCR 交互式软件 - 打包程序")
    print("MinGuo Newspaper OCR - Packaging Tool")
    print("=" * 60)
    print()
    
    # 检查 PyInstaller
    try:
        import PyInstaller
        print("✓ PyInstaller 已安装")
    except ImportError:
        print("✗ PyInstaller 未安装")
        print("  请运行: pip install pyinstaller")
        sys.exit(1)
    
    # 准备打包命令
    app_name = "MinGuoOCR_Interactive"
    script_name = "interactive_gui.py"
    
    # 检查脚本是否存在
    if not Path(script_name).exists():
        print(f"✗ 错误: {script_name} 不存在")
        sys.exit(1)
    
    print(f"✓ 找到主程序: {script_name}")
    print()
    
    # PyInstaller 命令
    cmd = [
        "pyinstaller",
        "--name", app_name,
        "--onefile",  # 打包成单个文件
        "--windowed",  # 不显示控制台窗口 (GUI应用)
        "--icon=NONE",  # 可以后续添加图标
        "--add-data", "config.json;.",  # 包含配置文件
        "--add-data", "layout;layout",  # 包含 layout 模块
        "--add-data", "recognizers;recognizers",  # 包含 recognizers 模块
        "--hidden-import", "PIL",
        "--hidden-import", "PIL._tkinter_finder",
        "--hidden-import", "cv2",
        "--hidden-import", "numpy",
        "--hidden-import", "dashscope",
        script_name
    ]
    
    print("开始打包...")
    print("命令:", " ".join(cmd))
    print()
    
    try:
        result = subprocess.run(cmd, check=True)
        print()
        print("=" * 60)
        print("✓ 打包完成！")
        print("=" * 60)
        print(f"可执行文件位置: dist/{app_name}.exe (Windows)")
        print(f"可执行文件位置: dist/{app_name} (Linux/Mac)")
        print()
        print("注意事项:")
        print("1. 首次运行前，需要在同目录下配置 config.json")
        print("2. 需要网络连接以访问 API 服务")
        print("3. 建议将整个 dist 文件夹分发给用户")
        print()
        
    except subprocess.CalledProcessError as e:
        print()
        print("✗ 打包失败")
        print(f"错误: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
