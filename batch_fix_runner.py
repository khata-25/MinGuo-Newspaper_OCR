import subprocess
import os
import sys

# ================= 配置区域 =================
# 在这里填入你想批量修复的文件夹名称列表
# 例如: ["10", "11", "12", "13"]
TARGET_FOLDERS = ["17", "18", "19", "32", "33", "34"]

# 使用强力修复模式 (V2, 缩放至 2500px, 解决 500 错误)
FIX_SCRIPT = "fix_failed_images_2.py"
# 或者使用普通修复模式
# FIX_SCRIPT = "fix_failed_images.py"

BASE_INPUT_DIR = "images"
BASE_OUTPUT_DIR = "output"
CONFIG_FILE = "config.json"
# ===========================================

def run_fix_batch():
    project_root = os.path.dirname(os.path.abspath(__file__))
    python_executable = sys.executable

    print(f"开始批量修复任务，共 {len(TARGET_FOLDERS)} 个文件夹...")
    print(f"使用修复脚本: {FIX_SCRIPT}")
    
    for folder in TARGET_FOLDERS:
        input_path = os.path.join(BASE_INPUT_DIR, folder)
        output_folder_name = f"full_batch_run_{folder}"
        output_path = os.path.join(BASE_OUTPUT_DIR, output_folder_name)
        
        # 检查输入目录
        abs_input_path = os.path.join(project_root, input_path)
        if not os.path.exists(abs_input_path):
            print(f"\n[跳过] 输入目录不存在: {input_path}")
            continue
            
        print(f"\n{'='*60}")
        print(f"正在修复文件夹: {folder}")
        print(f"输入: {input_path}")
        print(f"输出: {output_path}")
        print(f"{'='*60}")
        
        cmd = [
            python_executable, FIX_SCRIPT,
            "-i", input_path,
            "-o", output_path,
            "--config", CONFIG_FILE
        ]
        
        try:
            subprocess.run(cmd, check=False) 
            print(f"\n[完成] 文件夹 {folder} 修复流程结束。")
        except KeyboardInterrupt:
            print("\n[用户中断] 批量修复已停止。")
            sys.exit(0)
        except Exception as e:
            print(f"\n[错误] 运行修复脚本时发生未知错误: {e}")

    print(f"\n{'='*60}")
    print("所有批量修复任务已结束。")
    print(f"{'='*60}")

if __name__ == "__main__":
    run_fix_batch()
