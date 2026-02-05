# MinGuo-Newspaper_OCR
民国报纸 OCR 两阶段流水线（版面分割 -> 区域识别 -> Markdown 合并），支持异步 API、断点续传、失败任务修复与可视化校对。

## 工作流程总览
1. Stage 1 版面分割：输入整页图片，输出 layout.json 与 regions 切图。
2. Stage 2 区域识别：对每个区域 OCR，并写回 layout.json，同时生成单页 Markdown。
3. 合并输出：将所有单页 Markdown 合并为 merged_all.md。

## 目录结构（关键）
```
images/                      # 输入图片目录（按批次/文件夹管理）
output/                      # 输出目录
	full_batch_run_42/          # 示例批次输出
		42某报纸_01/              # 单页的 Stage 1 输出目录
			layout.json
			regions/0001.jpg
		42某报纸_01.md             # 单页识别结果
		merged_all.md              # 全部合并结果
```

## 环境准备
1. Python 3.9+（建议 3.10/3.11）
2. 安装依赖：
```
python -m pip install -r requirements.txt
```

> 注意：当前 requirements.txt 在某些环境下被识别为二进制文件，若无法读取，请先手动修复为纯文本再安装。

## 配置说明（config.json）
配置文件位于 [config.json](config.json)。

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

入口脚本：
- [main.py](main.py) 同步版
- [main_async.py](main_async.py) 异步版

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
默认开启：
- Stage 2 会跳过已有 `.md` 的页面。
- Stage 1 会跳过已有 `layout.json` 的页面。
如需重新处理，使用 `--no-resume`。

## 批量运行（多子文件夹）
修改脚本内的 `TARGET_FOLDERS` 后直接运行：
- 批量全流程：[batch_runner.py](batch_runner.py)
```
python batch_runner.py
```
- 批量 Stage 2：[batch_runner_stage2.py](batch_runner_stage2.py)
```
python batch_runner_stage2.py
```
- 批量修复：[batch_fix_runner.py](batch_fix_runner.py)
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

脚本位置：[fix_failed_images.py](fix_failed_images.py)、[processor_fix.py](processor_fix.py)

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

文件位置：[visualize.py](visualize.py)

## Windows 图形界面
双击运行 [START_GUI.bat](START_GUI.bat)，会启动 [gui_launcher.py](gui_launcher.py) 提供：
- 选择输入/输出路径
- 一键批量识别
- 修复失败任务
- 启动可视化界面

## 输出说明
单页输出：
- `output/full_batch_run_01/<图片名>.md`

合并输出：
- `output/full_batch_run_01/merged_all.md`

中间产物：
- `output/full_batch_run_01/<图片名>/layout.json`
- `output/full_batch_run_01/<图片名>/regions/*.jpg`

## 核心模块说明
- 处理器：[processor.py](processor.py)
- 异步处理器：[processor_async.py](processor_async.py)
- 版面 API 客户端：[layout/paddle_vl_api.py](layout/paddle_vl_api.py)
- 异步版面 API 客户端：[layout/paddle_vl_async_api.py](layout/paddle_vl_async_api.py)
- 识别器（Qwen VL）：[recognizers/qwen_vl.py](recognizers/qwen_vl.py)

## 常见问题与建议
- API 500/403：建议降低并发 `processing.concurrency`，优先使用 [main_async.py](main_async.py)。
- 结果为空：可运行修复脚本重新识别失败页面。
- 网络波动：直接重跑同命令，断点续传会跳过已完成页。
- 如果要使用本地 PPStructure，请补充 [layout/ppstructure.py](layout/ppstructure.py) 的实现。

## 参考运行说明
原始运行说明见 [使用说明.md](使用说明.md)。