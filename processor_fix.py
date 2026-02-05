import os
import cv2
import json
import logging
import numpy as np
from pathlib import Path
from typing import List, Optional

# 复用原有的核心组件
# 假设 processor.py, layout 文件夹, recognizers 文件夹都在项目根目录下
# 如果原本的 config 加载方式不同，这里需要适配
from processor import MinguoOCRProcessor, Stage1Splitter, Stage2Recognizer
from layout.base import LayoutRegion
from layout.paddle_vl_async_api import PaddleVLAsyncApiClient

# 继承原有的类，但覆盖关键方法
class FixStage1(Stage1Splitter):
    def __init__(self, config: dict):
        super().__init__(config)
        self.MAX_API_SIDE = 2500  # 限制 API 请求的最大边长，降低分辨率以避免 500 错误
        
        # 强制替换为异步 API 客户端
        layout_config = self.config.get('layout', {})
        if layout_config.get('engine') == 'paddlevl_api':
            api_url = layout_config.get('api_url')
            token = layout_config.get('token')
            # 异步任务通常需要更长超时时间
            self.paddlevl_api = PaddleVLAsyncApiClient(api_url, token, timeout=900)
        
    def _resize_image_for_api(self, image):
        """
        缩放图片以适应 API 限制
        返回: (缩放后的图片, 缩放比例)
        """
        h, w = image.shape[:2]
        max_side = max(h, w)
        
        # 如果图片本身就在安全范围内，不缩放
        if max_side <= self.MAX_API_SIDE:
            return image, 1.0
            
        # 计算缩放比例
        scale = self.MAX_API_SIDE / max_side
        new_w = int(w * scale)
        new_h = int(h * scale)
        
        resized_img = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_AREA)
        logging.info(f"  [Fix] 图片过大 ({w}x{h})，已缩放至 ({new_w}x{new_h}) 用于 API 分析，缩放比: {scale:.4f}")
        return resized_img, scale
    
    def process_image(self, image_path: str, output_base_dir: str) -> dict:
        """
        重写 Stage 1 处理逻辑：
        1. 缩放图片 -> API 获取坐标
        2. 还原坐标
        3. 切割高清原图
        """
        image_file = Path(image_path)
        image_name = image_file.stem
        
        # 创建输出目录
        output_image_dir = Path(output_base_dir) / image_name
        output_image_dir.mkdir(parents=True, exist_ok=True)
        regions_dir = output_image_dir / "regions"
        regions_dir.mkdir(exist_ok=True)
        
        # 读取原图
        image = cv2.imdecode(np.fromfile(str(image_path), dtype=np.uint8), cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError(f"无法读取图片: {image_path}")
            
        orig_h, orig_w = image.shape[:2]
        logger = logging.getLogger(__name__)

        regions = []
        
        # === 关键修改分支：API 模式 ===
        if self.paddlevl_api:
            logger.info("调用 PaddleOCR-VL API (Fix模式)...")
            
            # 1. 缩放图片
            api_image, scale_factor = self._resize_image_for_api(image)
            
            # 2. 保存临时图片供 API 上传
            temp_api_path = output_image_dir / "temp_api_upload.jpg"
            # 使用 85% 质量压缩，减少上传体积
            cv2.imencode('.jpg', api_image, [int(cv2.IMWRITE_JPEG_QUALITY), 85])[1].tofile(str(temp_api_path))
            
            try:
                # 3. 调用 API
                api_result = self.paddlevl_api.parse_image(str(temp_api_path))
                
                # 清理临时文件
                if temp_api_path.exists():
                    os.remove(temp_api_path)
                
                # 保存原始响应 (Optional)
                md_path = output_image_dir / f"{image_name}_paddlevl_raw_fix.md"
                with open(md_path, 'w', encoding='utf-8') as f:
                    f.write(api_result.get("markdown", ""))

                # 4. 解析结果并还原坐标
                api_regions = api_result.get("regions", [])
                for i, r in enumerate(api_regions):
                    # 获取缩放后的 bbox
                    # 注意：PaddleOCR API 返回的 bbox 可能是 [x1, y1, x2, y2]
                    # 我们需要确认 paddle_vl_api.py 里怎么处理的。
                    # 根据之前的 processor.py: bbox = [int(x) for x in r['bbox']]
                    # 假设 bbox 是 [x1, y1, x2, y2]
                    
                    bbox_scaled = r['bbox']
                    
                    # 还原坐标：除以 scale_factor
                    x1 = int(bbox_scaled[0] / scale_factor)
                    y1 = int(bbox_scaled[1] / scale_factor)
                    x2 = int(bbox_scaled[2] / scale_factor)
                    y2 = int(bbox_scaled[3] / scale_factor)
                    
                    # 边界保护
                    x1, y1 = max(0, x1), max(0, y1)
                    x2, y2 = min(orig_w, x2), min(orig_h, y2)
                    
                    if x2 <= x1 or y2 <= y1:
                        continue
                        
                    regions.append(LayoutRegion(
                        bbox=(x1, y1, x2, y2),
                        region_type=r['label'],
                        confidence=1.0,
                        image=None, # 稍后切原图
                        order=i
                    ))
                
                logger.info(f"API (Fix) 返回 {len(regions)} 个区域 (坐标已还原)")
                
            except Exception as e:
                logger.error(f"Fix模式 API 调用失败: {e}")
                raise e
        else:
            # 非 API 模式（本地），直接调用原逻辑，但也建议缩放吗？
            # 本地 PPStructure 如果内存够大可能不需要，但为了防爆内存也可以缩放
            # 这里暂时保持原样，主要修复 API 500 问题
            regions = self.layout_detector.detect(image)

        # === 后续逻辑：切割高清原图 ===
        # 注意：这里我们直接复用 processor.py 里的保存逻辑，
        # 但我们需要把 regions 里的 bbox 对应的图片切出来。
        # 由于我们手动构造了 LayoutRegion (image=None)，
        # processor.py 的后续代码会根据 bbox 从 image (原图) 切割。
        
        # 为了复用原本的保存逻辑，我们需要把这段代码逻辑复制过来或者调用父类方法？
        # 父类 process_image 把检测和保存耦合在一起了。
        # 最简单的办法是：把我们造好的 regions 列表有了，然后自己在这里执行保存。
        
        layout_meta = {
            "image_name": image_name,
            "image_size": [orig_w, orig_h],
            "total_regions": len(regions),
            "regions": []
        }
        
        for idx, region in enumerate(regions):
            region_id = f"{idx+1:04d}"
            region_image_path = regions_dir / f"{region_id}.jpg"
            
            # 从高清原图切割
            x1, y1, x2, y2 = region.bbox
            region_image_data = image[y1:y2, x1:x2].copy()
            
            # 保存
            cv2.imencode('.jpg', region_image_data, [cv2.IMWRITE_JPEG_QUALITY, 90])[1].tofile(str(region_image_path))
            
            # 记录元数据
            region_meta = {
                "id": region_id,
                "region_type": region.region_type,
                "bbox": list(region.bbox),
                "confidence": region.confidence,
                "order": region.order,
                "image_file": f"regions/{region_id}.jpg"
            }
            layout_meta["regions"].append(region_meta)
            
        # 保存 layout.json
        layout_json_path = output_image_dir / "layout.json"
        with open(layout_json_path, 'w', encoding='utf-8') as f:
            json.dump(layout_meta, f, ensure_ascii=False, indent=2)
            
        return layout_meta

class FixProcessor(MinguoOCRProcessor):
    def __init__(self, config: dict):
        super().__init__(config)
        # 替换 Stage 1 为修复版
        self.stage1 = FixStage1(config)
