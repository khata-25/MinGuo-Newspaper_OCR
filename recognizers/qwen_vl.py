"""Qwen VL 区域文字识别"""
import cv2
import base64
import numpy as np
from typing import Optional
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

logger = logging.getLogger(__name__)


class QwenVLRegionRecognizer:
    """
    Qwen VL 区域识别器
    
    专门用于识别版面分割后的单个区域
    """
    
    def __init__(self, config: dict):
        self.api_key = config.get('api_key')
        self.model = config.get('model', 'qwen-vl-max')
        self.timeout = config.get('timeout', 60)
        self.max_region_size = config.get('max_region_size', 1500)
        self._available = False
        
        self._init_client()
    
    def _init_client(self):
        """初始化 DashScope 客户端"""
        if not self.api_key or self.api_key == "sk-your-api-key-here":
            logger.error("Qwen VL API Key 未配置或无效")
            self._available = False
            return
        try:
            import dashscope
            dashscope.api_key = self.api_key
            self._available = True
            logger.info(f"Qwen VL 初始化成功 (model={self.model})")
        except ImportError:
            self._available = False
            logger.error("请安装 dashscope: pip install dashscope")
    
    def is_available(self) -> bool:
        return self._available
    
    def recognize_region(
        self, 
        image: np.ndarray, 
        region_type: str = 'text'
    ) -> str:
        """
        识别单个区域的文字，带重试机制
        
        Args:
            image: 区域图像 (BGR)
            region_type: 区域类型 (text, title, table)
            
        Returns:
            识别的文字
        """
        if not self._available:
            raise RuntimeError("Qwen VL 未初始化")
        
        from dashscope import MultiModalConversation
        import time
        
        # 预处理图像
        processed_image = self._preprocess_image(image)
        
        # 编码为 Base64
        img_base64 = self._encode_image(processed_image)
        
        # 构建提示词
        prompt = self._build_prompt(region_type)
        
        # 调用 API，带重试
        retry_count = 5  # 增加重试次数
        last_error = None
        for attempt in range(retry_count):
            try:
                messages = [{
                    "role": "user",
                    "content": [
                        {"image": f"data:image/jpeg;base64,{img_base64}"},
                        {"text": prompt}
                    ]
                }]
                
                response = MultiModalConversation.call(
                    model=self.model,
                    messages=messages,
                    timeout=self.timeout
                )
                
                # 检查状态码
                if hasattr(response, 'status_code'):
                    status_code = response.status_code
                    
                    if status_code == 200:
                        content = response.output.choices[0].message.content
                        if isinstance(content, list):
                            return content[0].get('text', '').strip()
                        return str(content).strip()
                        
                    elif status_code == 429:
                        # 速率限制，主动抛出异常进入 catch 进行重试
                        logger.warning(f"API Rate Limit (429), attempt {attempt+1}/{retry_count}")
                        raise ConnectionError("Throttling.RateQuota")
                        
                    elif status_code == 400:
                        # 检查是否为内容审核失败
                        code = getattr(response, 'code', '')
                        if code == 'DataInspectionFailed':
                             logger.error("API 内容审查拦截")
                             return "<!-- error: content_blocked --> **【内容被API屏蔽，请人工核对】**"
                
                # 其他错误情况
                logger.error(f"API 错误: {response}")
                raise RuntimeError(f"Qwen VL API 调用失败: {response}")
                    
            except Exception as e:
                if isinstance(e, KeyboardInterrupt):
                    raise

                # 增强的瞬时错误判断 (包含 429 引发的 ConnectionError)
                if self._is_transient_error(e):
                    last_error = e
                    # 指数退避: 2s, 4s, 8s, 16s... 增加基数
                    wait_time = 2 * (2 ** attempt) 
                    logger.warning(f"需重试错误: {str(e)[:50]}... | 等待 {wait_time}s")
                    if attempt < retry_count - 1:
                        time.sleep(wait_time)
                        continue

                    logger.error(f"重试耗尽，跳过此区域")
                    return "<!-- error: retry_exhausted --> **【API请求超时/受限，未获取结果】**"

                logger.error(f"识别失败（不可重试）: {e}")
                return ""  # 返回空字符串以继续处理

    def _is_transient_error(self, error: Exception) -> bool:
        import ssl

        name = type(error).__name__.lower()
        msg = str(error).lower()
        return (
            isinstance(error, (ssl.SSLError, TimeoutError, ConnectionError, OSError))
            or "timeout" in name
            or "readtimeout" in name
            or "connection" in name
            or "ratequota" in msg # 捕获手动抛出的 rate limit 信息
            or "throttling" in msg
        )

    
    def _preprocess_image(self, image: np.ndarray) -> np.ndarray:
        """预处理图像"""
        h, w = image.shape[:2]
        
        # 缩放到合适大小
        if max(h, w) > self.max_region_size:
            scale = self.max_region_size / max(h, w)
            image = cv2.resize(image, None, fx=scale, fy=scale)
        
        # 如果图像太小，放大以提高识别率
        min_size = 200
        if min(h, w) < min_size:
            scale = min_size / min(h, w)
            image = cv2.resize(image, None, fx=scale, fy=scale)
        
        return image
    
    def _encode_image(self, image: np.ndarray) -> str:
        """编码图像为 Base64"""
        _, buffer = cv2.imencode(
            '.jpg', 
            image, 
            [cv2.IMWRITE_JPEG_QUALITY, 90]
        )
        return base64.b64encode(buffer).decode('utf-8')
    
    def _build_prompt(self, region_type: str) -> str:
        """构建提示词"""
        base_prompt = """请识别这个区域中的文字。

要求：
1. 这是民国报纸的一部分，使用繁体中文，可能是竖排
2. 精确识别所有文字，不要遗漏
3. 按正确的阅读顺序输出（竖排从上到下，如有多列从右到左）
4. 适当添加标点符号以辅助阅读
5. 直接输出识别的文字，不要添加任何说明"""
        
        if region_type == 'title':
            return base_prompt + "\n6. 这是标题区域，请用 Markdown 标题格式输出"
        elif region_type == 'table':
            return base_prompt + "\n6. 这是表格区域，请尽量保持表格结构"
        else:
            return base_prompt


class QwenVLBatchRecognizer(QwenVLRegionRecognizer):
    """
    批量识别器，带有并发和速率控制
    """
    
    def __init__(self, config: dict):
        super().__init__(config)
        self.request_interval = config.get('request_interval', 1.0)
        self.concurrency = config.get('concurrency', 5)
        self._last_request_time = 0
        self._lock = threading.Lock()
    
    def recognize_regions(
        self, 
        regions: list,
        progress_callback=None
    ) -> list:
        """
        批量识别多个区域 (多线程)
        
        Args:
            regions: LayoutRegion 列表
            progress_callback: 进度回调函数
            
        Returns:
            识别结果列表
        """
        if not self.is_available():
            raise RuntimeError("Qwen VL 未初始化：请确认已安装 dashscope 且 API Key 有效")
        total = len(regions)
        completed_count = 0
        
        def process_single_region(region):
            # 速率控制
            self._wait_for_rate_limit()
            # ...process_single_region(region):
            # 速率控制
            self._wait_for_rate_limit()
            
            # 识别
            if region.image is not None:
                try:
                    text = self.recognize_region(
                        region.image, 
                        region.region_type
                    )
                    region.text = text
                except Exception as e:
                    logger.error(f"区域识别失败: {e}")
                    region.text = ""
            return region

        # 使用线程池并发处理
        with ThreadPoolExecutor(max_workers=self.concurrency) as executor:
            # 提交所有任务
            future_to_region = {
                executor.submit(process_single_region, region): region 
                for region in regions
            }
            
            # 获取结果
            for future in as_completed(future_to_region):
                region = future_to_region[future]
                try:
                    # 获取更新后的 region
                    _ = future.result()
                    
                    # 进度回调 (线程安全地更新计数)
                    with self._lock:
                        completed_count += 1
                        current = completed_count
                    
                    if progress_callback:
                        progress_callback(current, total, region)
                        
                except Exception as exc:
                    logger.error(f"任务异常: {exc}")
        
        return regions
    
    def _wait_for_rate_limit(self):
        """等待以满足速率限制 (线程安全)"""
        with self._lock:
            elapsed = time.time() - self._last_request_time
            if elapsed < self.request_interval:
                time.sleep(self.request_interval - elapsed)
            self._last_request_time = time.time()
