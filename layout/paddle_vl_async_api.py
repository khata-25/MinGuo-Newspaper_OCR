"""PaddleOCR-VL 异步 API 客户端（版面解析/Markdown 输出）"""
import base64
import logging
import os
import json
import time
import requests
from typing import Optional
from pathlib import Path

logger = logging.getLogger(__name__)

class PaddleVLAsyncApiClient:
    """
    调用 PaddleOCR-VL 异步 API 获取 Markdown 结果
    """
    
    JOB_URL = "https://paddleocr.aistudio-app.com/api/v2/ocr/jobs"
    MODEL = "PaddleOCR-VL-1.5"

    def __init__(self, api_url: str = None, token: str = None, timeout: int = 600):
        # api_url 参数保留以兼容接口，但在异步模式下主要使用 JOB_URL
        # 如果传入的 api_url 包含 'ocr/jobs'，则使用传入的，否则使用默认的
        if api_url and 'ocr/jobs' in api_url:
            self.api_url = api_url
        else:
            self.api_url = self.JOB_URL
            
        self.token = token
        # 异步任务通常需要较长时间，增加默认超时或者轮询控制
        self.timeout = timeout 

    def is_available(self) -> bool:
        return bool(self.token)

    def parse_image(self, file_path: str) -> dict:
        if not self.is_available():
            raise RuntimeError("PaddleOCR-VL API 未配置")

        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        headers = {
            "Authorization": f"bearer {self.token}",
        }

        optional_payload = {
            "useDocOrientationClassify": False,
            "useDocUnwarping": False,
            "useChartRecognition": False,
        }

        # 1. 提交任务
        data = {
            "model": self.MODEL,
            "optionalPayload": json.dumps(optional_payload)
        }
        
        logger.info(f"提交异步 OCR 任务: {file_path}")
        with open(file_path, "rb") as f:
            files = {"file": f}
            try:
                job_response = requests.post(self.api_url, headers=headers, data=data, files=files, timeout=60)
            except Exception as e:
                raise RuntimeError(f"任务提交请求失败: {e}")

        if job_response.status_code != 200:
            raise RuntimeError(f"任务提交失败: {job_response.status_code} {job_response.text}")

        job_id = job_response.json()["data"]["jobId"]
        logger.info(f"任务提交成功，Job ID: {job_id}，开始轮询...")

        # 2. 轮询结果
        start_time = time.time()
        jsonl_url = ""
        
        while True:
            # 检查总超时
            if time.time() - start_time > self.timeout:
                raise RuntimeError(f"等待任务 {job_id} 超时 ({self.timeout}s)")
                
            try:
                job_result_response = requests.get(f"{self.api_url}/{job_id}", headers=headers, timeout=30)
            except Exception as e:
                logger.warning(f"轮询请求异常: {e}，重试中...")
                time.sleep(5)
                continue
                
            if job_result_response.status_code != 200:
                logger.warning(f"轮询返回非 200: {job_result_response.status_code}，重试中...")
                time.sleep(5)
                continue
                
            state = job_result_response.json()["data"]["state"]
            
            if state == 'done':
                try:
                    extract_progress = job_result_response.json()['data']['extractProgress']
                    extracted_pages = extract_progress['extractedPages']
                    end_time_str = extract_progress['endTime']
                    logger.info(f"任务完成: 已提取 {extracted_pages} 页，结束时间 {end_time_str}")
                except:
                    logger.info("任务完成")
                    
                jsonl_url = job_result_response.json()['data']['resultUrl']['jsonUrl']
                break
                
            elif state == "failed":
                error_msg = job_result_response.json()['data'].get('errorMsg', 'Unknown error')
                raise RuntimeError(f"任务失败: {error_msg}")
                
            elif state in ['pending', 'running']:
                # 可选：打印进度
                # if state == 'running':
                #    logger.debug("任务运行中...")
                pass
            
            time.sleep(5)

        # 3. 获取并解析结果
        if not jsonl_url:
            raise RuntimeError("未获取到结果 URL")
            
        logger.info(f"获取结果 JSONL: {jsonl_url}")
        jsonl_response = requests.get(jsonl_url, timeout=60)
        jsonl_response.raise_for_status()
        
        lines = jsonl_response.text.strip().split('\n')
        if not lines:
            raise RuntimeError("结果为空")
            
        # 只要第一页（单图模式）
        first_line = lines[0]
        full_result = json.loads(first_line)["result"]
        layout_results = full_result.get("layoutParsingResults", [])
        
        if not layout_results:
            raise RuntimeError("LayoutParsingResults 为空")
            
        parsed_data = layout_results[0]
        
        # 保存调试信息
        debug_log = Path(file_path).parent / "api_response_debug_async.json"
        try:
            with open(debug_log, 'w', encoding='utf-8') as f:
                json.dump(full_result, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

        markdown = parsed_data.get("markdown", {}).get("text", "")
        
        # 提取区域
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
