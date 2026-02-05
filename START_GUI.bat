@echo off
chcp 65001
echo 正在启动民国报纸 OCR 工具箱...
echo 请确保已安装 Python 环境并安装了依赖 (pip install -r requirements.txt)

python gui_launcher.py

if %errorlevel% neq 0 (
    echo 程序异常退出或未找到 Python，请检查环境配置。
    pause
)
