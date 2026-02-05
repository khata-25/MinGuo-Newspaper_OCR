"""异步核心处理器
继承自原 processor.py，仅替换 Stage1 为异步 API 实现
"""
import logging
from processor import MinguoOCRProcessor, Stage1Splitter
from layout.paddle_vl_async_api import PaddleVLAsyncApiClient

logger = logging.getLogger(__name__)

class AsyncStage1Splitter(Stage1Splitter):
    """
    异步版面分割器
    强制使用 PaddleVLAsyncApiClient
    """
    def _init_layout_detector(self):
        """覆盖初始化方法，强制使用异步客户端"""
        logger.info("正在初始化 AsyncStage1Splitter...")
        
        layout_config = self.config.get('layout', {})
        
        # 强制使用异步客户端
        self.layout_detector = None
        
        api_url = layout_config.get('api_url')
        token = layout_config.get('token')
        # 默认给一个较长的超时时间
        timeout = layout_config.get('timeout', 1200) 
        
        logger.info(f"初始化异步 API 客户端 (超时: {timeout}s)")
        self.paddlevl_api = PaddleVLAsyncApiClient(api_url, token, timeout=timeout)

class AsyncMinguoOCRProcessor(MinguoOCRProcessor):
    """
    异步 OCR 处理器
    使用 AsyncStage1Splitter 替换原有的 Stage1
    """
    def __init__(self, config: dict):
        # 调用父类初始化
        # 父类会初始化 self.stage1 = Stage1Splitter(config)
        # 我们需要在 super().__init__ 之后替换它，或者重写 __init__
        # 为了保险起见（避免父类 Stage1 初始化做了太重的工作），我们这里还是让它初始化，然后覆盖
        super().__init__(config)
        
        # 覆盖 Stage 1 为异步版本
        logger.info("切换 Stage 1 为异步模式...")
        self.stage1 = AsyncStage1Splitter(config)
