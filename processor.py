"""核心处理器 - 两阶段流水线版本
Stage 1: 版面分割 + 区域保存
Stage 2: 区域识别 + 结果合并
"""
import cv2
import numpy as np
from pathlib import Path
from typing import List, Optional, Callable
import logging
import json
import base64

from layout.base import LayoutRegion
from layout.ppstructure import PPStructureLayoutDetector, SimpleFallbackDetector
from layout.paddle_vl_api import PaddleVLOCRApiClient
from recognizers.qwen_vl import QwenVLBatchRecognizer
from recognizers.paddle_ocr import PaddleOCRBatchRecognizer

logger = logging.getLogger(__name__)


class Stage1Splitter:
    """
    第一阶段：版面分割 + 区域保存
    
    输入: image.jpg
    输出: output/{image_name}/
        ├── layout.json (元数据、bbox、排序信息)
        └── regions/
            ├── 0001.jpg
            ├── 0002.jpg
            └── ...
    """
    
    def __init__(self, config: dict):
        self.config = config
        self._init_layout_detector()
    
    def _init_layout_detector(self):
        """初始化版面检测器"""
        layout_config = self.config.get('layout', {})
        engine = layout_config.get('engine', 'ppstructure')
        
        if engine == 'paddlevl_api':
            self.layout_detector = None
            api_url = layout_config.get('api_url')
            token = layout_config.get('token')
            timeout = layout_config.get('timeout', 120)
            self.paddlevl_api = PaddleVLOCRApiClient(api_url, token, timeout=timeout)
        else:
            self.layout_detector = PPStructureLayoutDetector(layout_config)
            
            if not self.layout_detector.is_available():
                logger.warning("PPStructure 不可用，使用网格分割后备方案")
                self.layout_detector = SimpleFallbackDetector(rows=3, cols=4)
            self.paddlevl_api = None
    
    def process_image(
        self,
        image_path: str,
        output_base_dir: str
    ) -> dict:
        """
        处理单张图片：版面分割 + 区域保存
        
        Args:
            image_path: 图片路径
            output_base_dir: 输出基目录
            
        Returns:
            layout.json 内容字典
        """
        image_file = Path(image_path)
        image_name = image_file.stem  # 不含扩展名
        
        # 创建输出目录结构
        output_image_dir = Path(output_base_dir) / image_name
        output_image_dir.mkdir(parents=True, exist_ok=True)
        
        regions_dir = output_image_dir / "regions"
        regions_dir.mkdir(exist_ok=True)
        
        # 读取图片
        image = cv2.imdecode(
            np.fromfile(image_path, dtype=np.uint8),
            cv2.IMREAD_COLOR
        )
        if image is None:
            raise ValueError(f"无法读取图片: {image_path}")
        
        logger.info(f"图片尺寸: {image.shape[1]}x{image.shape[0]}")
        
        regions = []
        
        # API 模式处理
        if self.paddlevl_api:
            logger.info("调用 PaddleOCR-VL API 进行处理...")
            try:
                api_result = self.paddlevl_api.parse_image(str(image_path))
                
                # 保存原始 Markdown 结果作为参考
                md_path = output_image_dir / f"{image_name}_paddlevl_raw.md"
                with open(md_path, 'w', encoding='utf-8') as f:
                    f.write(api_result.get("markdown", ""))
                logger.info(f"API 原始结果已保存: {md_path}")
                
                # 将 API 返回的区域转换为 LayoutRegion 对象
                api_regions = api_result.get("regions", [])
                for i, r in enumerate(api_regions):
                    # 转换 bbox 格式（确保是整数）
                    bbox = [int(x) for x in r['bbox']] 
                    
                    regions.append(LayoutRegion(
                        bbox=tuple(bbox),
                        region_type=r['label'],
                        confidence=1.0, # API 未返回置信度，默认为 1.0
                        image=None, # 后续统一截取
                        order=i
                    ))
                logger.info(f"API 返回 {len(regions)} 个区域")
                
            except Exception as e:
                logger.error(f"PaddleOCR-VL API 调用失败: {e}")
                raise e
        else:
            # 本地版面分割：优先使用 PaddleOCR PPStructure 版面检测
            logger.info("执行版面分割 (PPStructure)...")
            regions = self.layout_detector.detect(image)
        
        logger.info(f"检测到 {len(regions)} 个区域")
        
        # 兜底：若完全未检出，使用网格切割（从右到左，再从上到下）
        if not regions:
            logger.warning("PPStructure 未检出区域，使用网格分割兜底")
            fallback_detector = SimpleFallbackDetector(rows=3, cols=4)
            regions = fallback_detector.detect(image)
            logger.info(f"网格分割得到 {len(regions)} 个区域")
        
        if not regions:
            logger.warning("未检测到任何区域，尝试整图作为单一区域")
            regions = [LayoutRegion(
                bbox=(0, 0, image.shape[1], image.shape[0]),
                region_type='text',
                confidence=1.0,
                image=image,
                order=0
            )]
        
        # 保存区域图片和元数据
        layout_meta = {
            "image_name": image_name,
            "image_size": [image.shape[1], image.shape[0]],
            "total_regions": len(regions),
            "regions": []
        }
        
        for idx, region in enumerate(regions):
            region_id = f"{idx+1:04d}"
            region_image_path = regions_dir / f"{region_id}.jpg"
            
            # 保存区域图片
            region_image_data = None
            if region.image is not None and region.image.size > 0:
                region_image_data = region.image.copy()
            else:
                # 如果没有 image，从原图截取
                x1, y1, x2, y2 = region.bbox
                x1, y1, x2, y2 = max(0, x1), max(0, y1), min(image.shape[1], x2), min(image.shape[0], y2)
                if x2 > x1 and y2 > y1:
                    region_image_data = image[y1:y2, x1:x2].copy()
                else:
                    # 如果坐标有问题，记录日志并创建一个空白图像
                    logger.warning(f"区域 {region_id} 坐标无效: {region.bbox}")
                    region_image_data = np.zeros((1, 1, 3), dtype=np.uint8)
            
            if region_image_data is not None:
                # 确保是 uint8 类型
                if region_image_data.dtype != np.uint8:
                    region_image_data = region_image_data.astype(np.uint8)
                
                # 使用 numpy 读写来处理中文路径
                is_success, buffer = cv2.imencode('.jpg', region_image_data, [cv2.IMWRITE_JPEG_QUALITY, 90])
                if is_success:
                    buffer.tofile(str(region_image_path))
                else:
                    logger.warning(f"编码区域 {region_id} 失败")
            
            # 记录元数据
            region_meta = {
                "id": region_id,
                "region_type": region.region_type,
                "bbox": list(region.bbox),  # [x1, y1, x2, y2]
                "confidence": region.confidence,
                "order": region.order,
                "image_file": f"regions/{region_id}.jpg"
            }
            layout_meta["regions"].append(region_meta)
            
            logger.info(f"  保存区域 {region_id}: {region.region_type}")
        
        # 保存 layout.json
        layout_json_path = output_image_dir / "layout.json"
        with open(layout_json_path, 'w', encoding='utf-8') as f:
            json.dump(layout_meta, f, ensure_ascii=False, indent=2)
        
        logger.info(f"版面元数据: {layout_json_path}")
        return layout_meta


class Stage2Recognizer:
    """
    第二阶段：区域识别 + 结果合并
    
    输入: output/{image_name}/
        ├── layout.json
        └── regions/*.jpg
    输出: {image_name}.md
    """
    
    def __init__(self, config: dict):
        self.config = config
        self._init_recognizer()
    
    def _init_recognizer(self):
        """初始化识别器"""
        recognizer_engine = self.config.get('recognizer', {}).get('engine', 'qwen_vl')
        api_config = self.config.get('api', {}).get('qwen_vl', {})
        processing_config = self.config.get('processing', {})
        recognizer_config = {**api_config, **processing_config}
        
        if recognizer_engine == 'paddle_ocr':
            self.recognizer = PaddleOCRBatchRecognizer(recognizer_config)
        else:
            self.recognizer = QwenVLBatchRecognizer(recognizer_config)

    def _sort_regions(self, regions_meta: List[dict]) -> List[dict]:
        """对区域进行排序"""
        # 优先使用 order 字段排序
        if regions_meta and all('order' in r for r in regions_meta):
            return sorted(regions_meta, key=lambda x: x['order'])
        
        # 否则按位置排序 (Top-Down, Left-Right)
        return sorted(regions_meta, key=lambda x: (x['bbox'][1], x['bbox'][0]))
    
    def process_image(
        self,
        image_dir: str,
        output_md_path: str,
        progress_callback: Callable = None
    ) -> str:
        """
        处理单张图片：区域识别 + 合并
        
        Args:
            image_dir: 图片对应的输出目录（包含 layout.json + regions/）
            output_md_path: 输出 Markdown 文件路径
            progress_callback: 进度回调
            
        Returns:
            识别的完整 Markdown 文本
        """
        image_dir_path = Path(image_dir)
        
        # 读取 layout.json
        layout_json_path = image_dir_path / "layout.json"
        if not layout_json_path.exists():
            raise FileNotFoundError(f"layout.json 不存在: {layout_json_path}")
        
        with open(layout_json_path, 'r', encoding='utf-8') as f:
            layout_meta = json.load(f)
        
        image_name = layout_meta.get('image_name', 'unknown')
        logger.info(f"加载版面元数据: {image_name}")
        
        # 1. 排序
        sorted_regions_meta = self._sort_regions(layout_meta['regions'])
        logger.info(f"区域已排序，总共 {len(sorted_regions_meta)} 个区域")
        
        # 重建 LayoutRegion 对象列表，并保留 ID 映射
        regions = []
        regions_map = {} # id -> region_meta
        
        for region_meta in sorted_regions_meta:
            region_id = region_meta.get('id', 'unknown')
            regions_map[region_id] = region_meta
            
            region_image_path = image_dir_path / region_meta['image_file']
            
            # 读取区域图片
            region_image = cv2.imdecode(
                np.fromfile(str(region_image_path), dtype=np.uint8),
                cv2.IMREAD_COLOR
            )
            if region_image is None:
                logger.warning(f"无法读取区域图片: {region_image_path}")
                region_image = np.zeros((1, 1, 3), dtype=np.uint8)
            
            region = LayoutRegion(
                bbox=tuple(region_meta['bbox']),
                region_type=region_meta['region_type'],
                confidence=region_meta.get('confidence', 1.0),
                image=region_image,
                order=region_meta.get('order', 0)
            )
            # 临时附加 ID 属性以便后续合并使用
            region.id = region_id
            regions.append(region)
        
        # 执行识别
        logger.info("执行区域识别...")
        
        def region_progress(current, total, region):
            logger.info(f"  识别区域 {current}/{total}: {region.region_type}")
            if progress_callback:
                progress_callback(current, total)
        
        recognized_regions = self.recognizer.recognize_regions(
            regions,
            progress_callback=region_progress
        )
        
        # 2. 将识别文本写回 layout.json
        for region in recognized_regions:
            region_id = getattr(region, 'id', None)
            if region_id and region_id in regions_map:
                regions_map[region_id]['text'] = region.text
        
        # 保存更新后的 layout.json (包含 text)
        with open(layout_json_path, 'w', encoding='utf-8') as f:
            json.dump(layout_meta, f, ensure_ascii=False, indent=2)
        logger.info(f"已更新 layout.json 包含识别文本")
        
        # 合并结果
        logger.info("合并识别结果...")
        result = self._merge_results(recognized_regions, image_name)
        
        if not result.strip() or result.strip() == f"# {image_name}":
            raise RuntimeError("识别结果为空，未生成有效内容")
        
        # 保存 Markdown
        with open(output_md_path, 'w', encoding='utf-8') as f:
            f.write(result)
        
        logger.info(f"保存结果: {output_md_path}")
        return result
    
    def _merge_results(
        self,
        regions: List[LayoutRegion],
        image_name: str
    ) -> str:
        """合并识别结果为 Markdown"""
        lines = [f"# {image_name}\n"]
        seen = set()
        
        def normalize_text(text: str) -> str:
            return "".join(text.split())
        
        for region in regions:
            if not region.text:
                continue
                
            # 3. ID Injection
            region_id = getattr(region, 'id', '')
            if region_id:
                lines.append(f"<!-- region_id: {region_id} -->")
            
            normalized = normalize_text(region.text)
            if len(normalized) >= 30 and normalized in seen:
                continue
            if len(normalized) >= 30:
                seen.add(normalized)
            
            # 根据区域类型添加格式
            if region.region_type == 'title':
                lines.append(f"## {region.text}\n")
            elif region.region_type == 'table':
                lines.append(f"```\n{region.text}\n```\n")
            else:
                lines.append(region.text)
                lines.append("")  # 空行分隔
        
        return "\n".join(lines)


class MinguoOCRProcessor:
    """
    民国报纸 OCR 处理器 - 两阶段流水线
    
    支持三种模式：
    - stage='both': 同时执行阶段 1 和 2（默认）
    - stage=1: 仅执行版面分割（保存 layout.json + regions）
    - stage=2: 仅执行区域识别（需要已有 layout.json）
    """
    
    def __init__(self, config: dict):
        self.config = config
        self.stage1 = Stage1Splitter(config)
        self.stage2 = Stage2Recognizer(config)
    
    def process_image(
        self,
        image_path: str,
        output_dir: str,
        stage: str = 'both',
        progress_callback: Callable = None
    ) -> str:
        """
        处理单张图片
        
        Args:
            image_path: 图片路径
            output_dir: 输出目录
            stage: 'both', '1', or '2'
            progress_callback: 进度回调
            
        Returns:
            识别的完整文本（Markdown 格式）
        """
        image_file = Path(image_path)
        image_name = image_file.stem
        output_md_path = Path(output_dir) / f"{image_name}.md"
        
        if stage in ('1', 'both'):
            logger.info(f"[Stage 1] 版面分割: {image_file.name}")
            self.stage1.process_image(image_path, output_dir)
        
        if stage in ('2', 'both'):
            image_output_dir = Path(output_dir) / image_name
            logger.info(f"[Stage 2] 区域识别: {image_name}")
            result = self.stage2.process_image(
                str(image_output_dir),
                str(output_md_path),
                progress_callback
            )
            return result
        
        return ""
    
    def process_folder(
        self,
        input_dir: str,
        output_dir: str,
        stage: str = 'both',
        resume: bool = True
    ) -> dict:
        """
        处理整个文件夹
        
        Args:
            input_dir: 输入目录
            output_dir: 输出目录
            stage: 'both', '1', or '2'
            resume: 是否跳过已处理的文件
            
        Returns:
            处理统计
        """
        input_path = Path(input_dir)
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # 获取图片/文件夹列表
        if stage == '2':
            # Stage 2: 输入是 Stage 1 的输出目录，包含子目录 {image_name}/
            # 查找所有包含 layout.json 的目录
            image_items = []
            for item in sorted(input_path.iterdir()):
                if item.is_dir() and (item / "layout.json").exists():
                    image_items.append(item)
        else:
            # Stage 1 或 both: 输入是原始图片目录
            image_items = sorted(
                list(input_path.glob("*.png")) +
                list(input_path.glob("*.jpg")) +
                list(input_path.glob("*.jpeg"))
            )
        
        stats = {
            "total": len(image_items),
            "success": 0,
            "failed": 0,
            "skipped": 0
        }
        
        all_results = []
        
        for item in image_items:
            if stage == '2':
                # item 是包含 layout.json 的目录
                image_name = item.name
                output_file = output_path / f"{image_name}.md"
                image_output_dir = item
            else:
                # item 是图片文件
                img_path = item
                image_name = img_path.stem
                output_file = output_path / f"{image_name}.md"
                image_output_dir = output_path / image_name
            
            # 断点续传逻辑
            if resume and stage in ('both', '2'):
                # 对于 Stage 2 或 both，检查最终输出
                if output_file.exists():
                    logger.info(f"跳过已处理: {image_name}")
                    stats["skipped"] += 1
                    with open(output_file, 'r', encoding='utf-8') as f:
                        all_results.append(f.read())
                    continue
            elif resume and stage == '1':
                # 对于 Stage 1，检查是否已有 layout.json
                layout_json = image_output_dir / "layout.json"
                if layout_json.exists():
                    logger.info(f"跳过已处理: {image_name}")
                    stats["skipped"] += 1
                    continue
            
            try:
                logger.info(f"处理: {image_name}")
                
                if stage == '2':
                    # Stage 2: 直接处理 layout 目录
                    result = self.stage2.process_image(
                        str(image_output_dir),
                        str(output_file)
                    )
                    if result:
                        all_results.append(result)
                else:
                    # Stage 1 或 both: 从图片文件开始
                    result = self.process_image(
                        str(item),
                        str(output_path),
                        stage=stage
                    )
                    if result:  # Stage 2 或 both 会返回结果
                        all_results.append(result)
                
                stats["success"] += 1
                if stage in ('both', '2'):
                    logger.info(f"  ✅ 保存: {output_file.name}")
                else:
                    logger.info(f"  ✅ Stage 1 完成: {image_output_dir.name}")
                
            except Exception as e:
                stats["failed"] += 1
                logger.error(f"  ❌ 失败: {e}")
                import traceback
                logger.debug(traceback.format_exc())
        
        # 仅在 Stage 2 或 both 时合并结果
        if all_results and stage in ('both', '2'):
            merged_file = output_path / "merged_all.md"
            with open(merged_file, 'w', encoding='utf-8') as f:
                f.write(f"# 合并文档\n\n")
                f.write("---\n\n".join(all_results))
            logger.info(f"合并文档: {merged_file}")
        
        return stats
