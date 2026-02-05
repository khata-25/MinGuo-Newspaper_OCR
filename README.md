# MinGuo-Newspaper_OCR
民国报纸 OCR 两阶段流水线（版面分割 -> 区域识别 -> Markdown 合并）。

本项目默认使用 PaddleOCR-VL API 做版面解析（Stage 1），使用 Qwen VL 做区域文字识别（Stage 2），支持断点续传、异步 API、失败任务修复与可视化校对。

## 主要流程
1. Stage 1（版面分割）：对整页图像进行版面分析，输出区域切图与 layout.json。
2. Stage 2（区域识别）：对区域切图进行 OCR，写回 layout.json，并生成单页 Markdown。
3. 合并输出：将所有单页 Markdown 合并为 merged_all.md。

## 目录结构（关键）
```
images/                    # 输入图片目录（按批次/文件夹管理）
output/                    # 输出目录
	full_batch_run_42/        # 示例批次输出
		42某报纸_01/            # 单页的 Stage 1 输出目录
			layout.json
			regions/0001.jpg
		42某报纸_01.md           # 单页识别结果
		merged_all.md            # 全部合并结果
```

## 环境准备
1. Python 3.9+（建议 3.10/3.11）
2. 安装依赖：
```
python -m pip install -r requirements.txt
```

> 提示：如果你使用了 Qwen VL，需要安装 `dashscope`，若缺失会在运行时提示安装。

## 配置说明（config.json）
需要配置两类 API：
- PaddleOCR-VL（版面解析）：`layout.api_url` 与 `layout.token`
- Qwen VL（文字识别）：`api.qwen_vl.api_key`

关键字段：
- `layout.engine`：默认 `paddlevl_api`（走 API）。
- `recognizer.engine`：默认 `qwen_vl`。
- `processing.concurrency`：并发数量，网络不稳定时适当调小。
- `processing.request_interval`：请求间隔（秒）。

## 快速开始（推荐）
异步版更稳定，适合批量和网络波动场景：
```
python main_async.py -i images/42 -o output/full_batch_run_42
```

同步版：
```
python main.py -i images/42 -o output/full_batch_run_42
```

## 运行模式
### 1) 全流程（Stage 1 + Stage 2）
```
python main.py -i images/01 -o output/full_batch_run_01
```

### 2) 仅 Stage 1（版面切割）
```
python main.py -i images/01 -o output/full_batch_run_01 --stage 1
```

### 3) 仅 Stage 2（识别合并）
```
python main.py -i output/full_batch_run_01 -o output/full_batch_run_01 --stage 2
```

### 4) 重新全量运行（忽略断点续传）
```
python main.py -i images/01 -o output/full_batch_run_01 --no-resume
```

## 断点续传
默认开启。Stage 2 会跳过已有 `.md` 的页面；Stage 1 会跳过已有 `layout.json` 的页面。
如需重新处理，使用 `--no-resume`。

## 批量运行（多子文件夹）
在脚本中修改目标文件夹列表后直接运行：
- 批量全流程：
```
python batch_runner.py
```
- 批量 Stage 2：
```
python batch_runner_stage2.py
```
- 批量修复：
```
python batch_fix_runner.py
```

## 失败任务修复
### 1) 修复脚本（推荐：异步 API + 缩放）
```
python fix_failed_images.py -i images/42 -o output/full_batch_run_42
```
说明：
- 自动扫描缺失或过短的 `.md` 文件。
- 强制降低并发（默认 2），提高稳定性。
- 对过大图片进行缩放后请求 API，再还原坐标切图。

### 2) 强力修复脚本 V2
```
python fix_failed_images_2.py -i images/42 -o output/full_batch_run_42
```
注意：该脚本依赖 `processor_fix2.py`，当前仓库未包含此文件，请先补充或改用上面的修复脚本。

## 可视化校对（Streamlit）
```
pip install streamlit
streamlit run visualize.py
```
功能：
- 图片叠加区域框
- 区域文字列表
- 搜索与定位

## 输出说明
单页输出：
- `output/full_batch_run_01/<图片名>.md`

合并输出：
- `output/full_batch_run_01/merged_all.md`

中间产物：
- `output/full_batch_run_01/<图片名>/layout.json`
- `output/full_batch_run_01/<图片名>/regions/*.jpg`

## 常见问题与建议
- API 500/403：建议降低并发 `processing.concurrency`，优先使用 `main_async.py`。
- 结果为空：可运行修复脚本重新识别失败页面。
- 网络波动：直接重跑同命令，断点续传会跳过已完成页。

## 运行入口速览
- 全流程：`main.py` / `main_async.py`
- 批量：`batch_runner.py` / `batch_runner_stage2.py` / `batch_fix_runner.py`
- 修复：`fix_failed_images.py` / `fix_failed_images_2.py`
- 可视化：`visualize.py`
- GUI（Windows）：`START_GUI.bat`