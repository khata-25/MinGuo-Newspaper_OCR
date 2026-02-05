import argparse
import json
import logging
import sys
import traceback
from pathlib import Path

# 导入配置和新的处理器 V2
from processor_fix2 import FixProcessorV2

'''
此脚本用于处理第一轮 fix 仍然失败的“顽固分子”。
它使用更强力的缩放 (2500px) 来确保通过 API 审查和内存限制。
'''

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - FIX_TASK_V2 - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

def main():
    parser = argparse.ArgumentParser(description="民国报纸 OCR - 失败任务专项修复工具 V2 (强力缩放版)")
    parser.add_argument('-i', '--input', required=True, help="原始图片目录 (如 images/12)")
    parser.add_argument('-o', '--output', required=True, help="已有的输出目录 (如 output/full_batch_run_12)")
    parser.add_argument('--config', default='config.json', help="配置文件路径")
    
    args = parser.parse_args()
    
    # 1. 加载配置
    config_path = Path(args.config)
    if not config_path.exists():
        logging.error(f"配置文件未找到: {config_path}")
        return
        
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
        
    # 强制修改并发数为 1 (V2 模式求稳不求快)
    config['processing']['concurrency'] = 1
    logging.info("已自动将并发数调整为 1 以提高稳定性 (V2模式)")

    # 2. 初始化修复版处理器 V2
    try:
        processor = FixProcessorV2(config)
    except Exception as e:
        logging.error(f"处理器初始化失败: {e}")
        return

    input_dir = Path(args.input)
    output_dir = Path(args.output)
    
    if not input_dir.exists():
        logging.error(f"输入目录不存在: {input_dir}")
        return

    # 3. 扫描并找出失败任务
    all_images = sorted([
        f for f in input_dir.iterdir() 
        if f.suffix.lower() in ['.jpg', '.png', '.jpeg']
    ])
    
    failed_tasks = []
    skipped_count = 0
    
    logging.info(f"正在扫描目录 {input_dir} 下的失败任务...")
    
    for img_path in all_images:
        image_name = img_path.stem
        md_file = output_dir / f"{image_name}.md"
        
        is_success = False
        if md_file.exists():
            # 检查文件大小
            if md_file.stat().st_size > 500:
                is_success = True
        
        if is_success:
            skipped_count += 1
        else:
            failed_tasks.append(img_path)
    
    # 如果没有失败任务，但用户还是运行了这个脚本，可能是因为想重新跑某些“似乎成功但其实有问题”的
    # 不过这里还是保持逻辑一致，只跑缺失的。
            
    logging.info(f"扫描完成: 总计 {len(all_images)}，已完成 {skipped_count}，待修复 {len(failed_tasks)}")
    
    if not failed_tasks:
        logging.info("所有任务看起来都已完成，无需修复。")
        return

    # 4. 执行修复
    success_fix = 0
    failed_fix = 0
    
    for idx, img_path in enumerate(failed_tasks):
        image_name = img_path.stem
        logging.info(f"\n[{idx+1}/{len(failed_tasks)}] 开始修复 (V2): {image_name}")
        
        try:
            # 这里的 process_image 会调用我们重写的 FixStage1_V2
            result = processor.process_image(
                str(img_path),
                str(output_dir),
                stage='both' 
            )
            
            if result:
                success_fix += 1
                logging.info(f"✅ 修复成功: {image_name}")
            else:
                failed_fix += 1
                logging.error(f"❌ 修复失败 (无结果): {image_name}")
                
        except Exception as e:
            failed_fix += 1
            logging.error(f"❌ 修复过程异常: {image_name} - {e}")
            logging.debug(traceback.format_exc())

    # 5. 重新合并结果
    logging.info("\n正在更新 merged_all.md...")
    try:
        all_md_content = []
        for img_path in all_images: 
            md_path = output_dir / f"{img_path.stem}.md"
            if md_path.exists():
                with open(md_path, 'r', encoding='utf-8') as f:
                    all_md_content.append(f.read())
        
        merged_file = output_dir / "merged_all.md"
        with open(merged_file, 'w', encoding='utf-8') as f:
            f.write(f"# 合并文档 ({len(all_md_content)}页)\n\n")
            f.write("---\n\n".join(all_md_content))
        logging.info("合并文档已更新。")
    except Exception as e:
        logging.warning(f"合并文档更新失败: {e}")

    logging.info(f"\n修复汇总: 尝试 {len(failed_tasks)}，成功 {success_fix}，失败 {failed_fix}")

if __name__ == "__main__":
    main()
