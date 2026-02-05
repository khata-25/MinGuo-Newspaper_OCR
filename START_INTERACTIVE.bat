@echo off
chcp 65001
echo ========================================
echo 民国报纸 OCR 交互式识别软件
echo Interactive MinGuo Newspaper OCR
echo ========================================
echo.
echo 正在启动交互式识别界面...
echo 请确保已安装 Python 环境并安装了依赖
echo (pip install -r requirements.txt)
echo.

python interactive_gui.py

if %errorlevel% neq 0 (
    echo.
    echo 程序异常退出或未找到 Python，请检查环境配置。
    echo.
    pause
)
