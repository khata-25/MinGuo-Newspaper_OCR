"""PaddleOCR-VL API 客户端（版面解析/Markdown 输出）"""
import base64
import logging
import os
from typing import Optional
from pathlib import Path

import requests

logger = logging.getLogger(__name__)


class PaddleVLOCRApiClient:
    """
    调用 PaddleOCR-VL API 获取 Markdown 结果
    
    注意：该接口直接返回 Markdown 文本与图像链接。
    """

    def __init__(self, api_url: str, token: str, timeout: int = 120):
        self.api_url = api_url
        self.token = token
        self.timeout = timeout

    def is_available(self) -> bool:
        return bool(self.api_url and self.token)

    def parse_image(self, file_path: str) -> str:
        if not self.is_available():
            raise RuntimeError("PaddleOCR-VL API 未配置")

        with open(file_path, "rb") as file:
            file_bytes = file.read()
        file_data = base64.b64encode(file_bytes).decode("ascii")

        headers = {
            "Authorization": f"token {self.token}",
            "Content-Type": "application/json"
        }

        payload = {
            "file": file_data,
            "fileType": 1,
            "useDocOrientationClassify": False,
            "useDocUnwarping": False,
            "useChartRecognition": False,
        }

        response = requests.post(self.api_url, json=payload, headers=headers, timeout=self.timeout)
        if response.status_code != 200:
            raise RuntimeError(f"PaddleOCR-VL API 失败: {response.status_code} {response.text}")

        result = response.json().get("result", {})
        layout_results = result.get("layoutParsingResults", [])
        if not layout_results:
            raise RuntimeError("PaddleOCR-VL API 返回为空")

        # 调试：保存原始响应以便分析 layout
        import json
        debug_log = Path(file_path).parent / "api_response_debug.json"
        with open(debug_log, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        # 默认取第一个结果
        parsed_data = layout_results[0]
        markdown = parsed_data.get("markdown", {}).get("text", "")
        
        # 提取版面区域信息
        regions = []
        parsing_res_list = parsed_data.get("prunedResult", {}).get("parsing_res_list", [])
        for block in parsing_res_list:
            bbox = block.get("block_bbox")
            if bbox and len(bbox) == 4:
                regions.append({
                    "bbox": bbox, # [x1, y1, x2, y2]
                    "label": block.get("block_label", "text"),
                    "text": block.get("block_content", "") 
                })

        return {
            "markdown": markdown,
            "regions": regions
        }
