"""民国报纸 OCR 处理程序 (异步版)
专门用于调用 PaddleOCR-VL 异步接口，适合网络不稳定或大批量处理场景。
无需修改 config.json 即可使用。
"""
import argparse
import json
import logging
import sys
from pathlib import Path

# 导入新的异步处理器
from processor_async import AsyncMinguoOCRProcessor

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - ASYNC_MAIN - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

def main():
    parser = argparse.ArgumentParser(description="民国报纸 OCR 处理程序 (Hybrid Parallel - 异步版)")
    parser.add_argument('-i', '--input', required=True, help="输入图片目录")
    parser.add_argument('-o', '--output', required=True, help="输出结果目录")
    parser.add_argument('--stage', choices=['1', '2', 'both'], default='both', help="执行阶段: 1(版面), 2(识别), both(全部)")
    parser.add_argument('--no-resume', action='store_true', help="不使用断点续传（重新处理）")
    parser.add_argument('--config', default='config.json', help="配置文件路径")
    
    args = parser.parse_args()
    
    # 加载配置
    config_path = Path(args.config)
    if not config_path.exists():
        logging.error(f"配置文件未找到: {config_path}")
        sys.exit(1)
        
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
        
    # 初始化异步处理器
    try:
        logging.info("初始化异步处理器...")
        processor = AsyncMinguoOCRProcessor(config)
        
        # 运行处理
        logging.info(f"开始异步处理: {args.input} -> {args.output}")
        logging.info(f"阶段: {args.stage}, 断点续传: {not args.no_resume}")
        
        stats = processor.process_folder(
            args.input,
            args.output,
            stage=args.stage,
            resume=not args.no_resume
        )
        
        logging.info("异步处理完成!")
        logging.info(f"统计: {json.dumps(stats, indent=2)}")
        
    except Exception as e:
        logging.error(f"程序运行出错: {e}")
        import traceback
        logging.error(traceback.format_exc())
        sys.exit(1)

if __name__ == '__main__':
    main()
