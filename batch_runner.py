import subprocess
import os
import sys

# ================= 配置区域 =================
# 在这里填入你想处理的文件夹名称列表
# 例如: ["04", "05", "06", "07"]
TARGET_FOLDERS = ["43", "44", "45", "46"]

# 基础目录配置
BASE_INPUT_DIR = "images"
BASE_OUTPUT_DIR = "output"

# 其他参数 (例如配置 config.json)
CONFIG_FILE = "config.json"
# ===========================================

def run_batch():
    project_root = os.path.dirname(os.path.abspath(__file__))
    
    # 兼容Windows Powershell, 确保能找到 python
    python_executable = sys.executable

    print(f"开始批量处理任，共 {len(TARGET_FOLDERS)} 个文件夹...")
    
    for folder in TARGET_FOLDERS:
        # 构建路径
        input_path = os.path.join(BASE_INPUT_DIR, folder)
        # 自动生成对应的输出目录名，例如 output/full_batch_run_04
        output_folder_name = f"full_batch_run_{folder}"
        output_path = os.path.join(BASE_OUTPUT_DIR, output_folder_name)
        
        # 检查输入目录是否存在
        abs_input_path = os.path.join(project_root, input_path)
        if not os.path.exists(abs_input_path):
            print(f"\n[跳过] 输入目录不存在: {input_path}")
            continue

        print(f"\n{'='*60}")
        print(f"正在处理文件夹: {folder}")
        print(f"输入: {input_path}")
        print(f"输出: {output_path}")
        print(f"{'='*60}")
        
        # 构建命令行命令
        # 相当于执行: python main.py -i images/04 -o output/full_batch_run_04 --config config.json
        cmd = [
            python_executable, "main_async.py",
            "-i", input_path,
            "-o", output_path,
            "--config", CONFIG_FILE
        ]
        
        try:
            # check=True 会在命令执行失败(非0退出码)时抛出异常
            subprocess.run(cmd, check=True)
            print(f"\n[成功] 文件夹 {folder} 处理完毕。")
        except subprocess.CalledProcessError as e:
            print(f"\n[错误] 处理文件夹 {folder} 时发生错误。退出码: {e.returncode}")
            # 你可以选择在这里 break 停止所有任务，或者 continue 继续下一个
            # continue 
        except KeyboardInterrupt:
            print("\n[用户中断] 批量任务已停止。")
            sys.exit(0)

    print(f"\n{'='*60}")
    print("所有批量任务已结束。")
    print(f"{'='*60}")

if __name__ == "__main__":
    run_batch()
