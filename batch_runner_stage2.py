import subprocess
import os
import sys

# ================= 配置区域 =================
# 在这里填入你想处理的文件夹名称列表
# 例如: ["18", "19", "32", "33", "34"]
TARGET_FOLDERS = ["18", "19", "32", "33", "34"]

# 基础目录配置（Stage 2 输入为 output/full_batch_run_xx）
BASE_OUTPUT_DIR = "output"

# 其他参数 (例如配置 config.json)
CONFIG_FILE = "config.json"
# ===========================================


def run_batch_stage2():
    project_root = os.path.dirname(os.path.abspath(__file__))

    # 兼容 Windows Powershell, 确保能找到 python
    python_executable = sys.executable

    print(f"开始批量执行 Stage 2，共 {len(TARGET_FOLDERS)} 个文件夹...")

    for folder in TARGET_FOLDERS:
        # Stage 2 输入与输出目录一致
        output_folder_name = f"full_batch_run_{folder}"
        input_path = os.path.join(BASE_OUTPUT_DIR, output_folder_name)
        output_path = input_path

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
        # 相当于执行: python main.py -i output/full_batch_run_18 -o output/full_batch_run_18 --stage 2 --config config.json
        cmd = [
            python_executable, "main.py",
            "-i", input_path,
            "-o", output_path,
            "--stage", "2",
            "--config", CONFIG_FILE
        ]

        try:
            subprocess.run(cmd, check=True)
            print(f"\n[成功] 文件夹 {folder} Stage 2 完成。")
        except subprocess.CalledProcessError as e:
            print(f"\n[错误] 处理文件夹 {folder} 时发生错误。退出码: {e.returncode}")
        except KeyboardInterrupt:
            print("\n[用户中断] 批量任务已停止。")
            sys.exit(0)

    print(f"\n{'='*60}")
    print("所有 Stage 2 批量任务已结束。")
    print(f"{'='*60}")


if __name__ == "__main__":
    run_batch_stage2()
