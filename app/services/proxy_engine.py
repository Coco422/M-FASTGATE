"""
通用代理转发引擎 - v0.2.0
实现HTTP/HTTPS协议转发、流式响应处理、错误处理和重试机制
"""

import asyncio
import httpx
import json
from typing import Dict, Any, Optional, AsyncGenerator, List
from fastapi import HTTPException, Response
from fastapi.responses import StreamingResponse
import structlog

from ..config import settings

logger = structlog.get_logger(__name__)


class ProxyEngine:
    """通用代理转发引擎"""
    
    def __init__(self):
        """初始化代理引擎"""
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(
                connect=10.0,
                read=settings.proxy['timeout'],
                write=10.0,
                pool=None
            ),
            limits=httpx.Limits(max_keepalive_connections=100, max_connections=200),
            follow_redirects=True
        )
        self.logger = logger.bind(service="proxy_engine")
    
    async def forward_request(
        self,
        route_config: Dict[str, Any],
        method: str,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
        content: Optional[bytes] = None,
        is_stream_request: bool = False,  # 新增：标识是否为流式请求
        **kwargs
    ) -> httpx.Response:
        """
        转发HTTP请求到目标服务器
        
        Args:
            route_config: 路由配置
            method: HTTP方法
            url: 目标URL
            headers: 请求头
            params: 查询参数
            json: JSON请求体
            content: 原始请求体
            is_stream_request: 是否为流式请求
            **kwargs: 其他请求参数
            
        Returns:
            httpx.Response: 响应对象
            
        Raises:
            HTTPException: 转发失败时抛出
        """
        timeout = route_config.get('timeout', settings.proxy.get('timeout', 30))
        retry_count = route_config.get('retry_count', settings.proxy.get('max_retries', 0))
        
        # 处理请求头
        processed_headers = self._process_headers(headers or {}, route_config)
        
        # 构建请求参数
        request_kwargs = {
            "method": method,
            "url": url,
            "headers": processed_headers,
            "timeout": timeout
        }
        
        if params:
            request_kwargs["params"] = params
            
        if json is not None:
            request_kwargs["json"] = self._process_request_body(json, route_config)
        elif content is not None:
            request_kwargs["content"] = content
        
        # 添加其他参数
        request_kwargs.update(kwargs)
        
        last_exception = None
        
        # 执行请求（带重试）
        for attempt in range(retry_count + 1):
            try:
                # 调试日志：记录改造后的请求头和请求体
                self.logger.debug(
                    "Proxy request details",
                    method=method,
                    url=url,
                    processed_headers=processed_headers,
                    processed_body=request_kwargs.get("json"),
                    content_length=len(str(request_kwargs.get("content", ""))) if request_kwargs.get("content") else 0,
                    attempt=attempt + 1
                )
                
                self.logger.info(
                    "Forwarding request",
                    method=method,
                    url=url,
                    attempt=attempt + 1,
                    max_attempts=retry_count + 1,
                    is_stream=is_stream_request
                )
                
                # 关键修复：对于流式请求，使用stream方法立即返回
                if is_stream_request:
                    # 使用stream方法，立即返回响应对象，不等待内容
                    stream_response = self.client.stream(**request_kwargs)
                    response = await stream_response.__aenter__()
                else:
                    response = await self.client.request(**request_kwargs)
                
                self.logger.info(
                    "Request forwarded successfully",
                    status_code=response.status_code,
                    content_type=response.headers.get("content-type", ""),
                    headers_size=len(str(response.headers))
                )
                
                return response
                
            except (httpx.ConnectError, httpx.TimeoutException, httpx.ReadTimeout) as e:
                last_exception = e
                self.logger.warning(
                    "Request failed, retrying",
                    error=str(e),
                    attempt=attempt + 1,
                    max_attempts=retry_count + 1
                )
                
                if attempt < retry_count:
                    # 指数退避重试
                    await asyncio.sleep(min(2 ** attempt, 10))
                    continue
                else:
                    break
                    
            except httpx.HTTPStatusError as e:
                # HTTP状态码错误不重试，直接返回响应
                self.logger.warning(
                    "HTTP error response",
                    status_code=e.response.status_code,
                    url=url
                )
                return e.response
                
            except Exception as e:
                last_exception = e
                self.logger.error(
                    "Unexpected error during request",
                    error=str(e),
                    error_type=type(e).__name__
                )
                break
        
        # 所有重试都失败了
        error_msg = f"Request failed after {retry_count + 1} attempts"
        if last_exception:
            error_msg += f": {str(last_exception)}"
            
        self.logger.error("Request forwarding failed", error=error_msg)
        raise HTTPException(status_code=502, detail=error_msg)
    
    async def handle_stream_response(self, response: httpx.Response, audit_service=None, request_id=None) -> StreamingResponse:
        """
        纯净流式响应处理 - 无审计版本
        
        Args:
            response: 原始响应对象
            audit_service: 审计服务实例（忽略）
            request_id: 请求ID（忽略）
            
        Returns:
            StreamingResponse: FastAPI流式响应
        """
        self.logger.info(
            "Handling stream response - pure mode",
            status_code=response.status_code,
            content_type=response.headers.get("content-type", "")
        )
        
        async def stream_wrapper() -> AsyncGenerator[bytes, None]:
            """纯净流式响应包装器 - 无任何阻塞操作"""
            try:
                # 直接转发流式响应，无任何额外处理
                async for chunk in response.aiter_bytes(chunk_size=1024):
                    if chunk:
                        yield chunk
                        
            except Exception as e:
                self.logger.error("Stream error", error=str(e))
                raise
            finally:
                await response.aclose()
        
        # 优化响应头，强制无缓冲  
        response_headers = self._process_response_headers(dict(response.headers))
        
        return StreamingResponse(
            stream_wrapper(),
            status_code=response.status_code,
            headers=response_headers,
            media_type=response.headers.get("content-type", "application/octet-stream")
        )
    
    def _process_headers(self, headers: Dict[str, str], route_config: Dict[str, Any]) -> Dict[str, str]:
        """
        处理请求头
        
        Args:
            headers: 原始请求头
            route_config: 路由配置
            
        Returns:
            Dict[str, str]: 处理后的请求头
        """
        processed_headers = headers.copy()
        
        # 移除指定的请求头
        strip_headers = settings.proxy.get('strip_headers', [])
        remove_headers = route_config.get('remove_headers', [])
        
        # 如果remove_headers是字符串，尝试解析为JSON
        if isinstance(remove_headers, str):
            try:
                remove_headers = json.loads(remove_headers)
            except (json.JSONDecodeError, TypeError):
                remove_headers = []
        
        # 确保remove_headers是列表类型
        if remove_headers is None:
            remove_headers = []
        
        for header_name in strip_headers + remove_headers:
            processed_headers.pop(header_name.lower(), None)
        
        # 添加新的请求头
        add_headers = route_config.get('add_headers', {})
        
        # 如果add_headers是字符串，尝试解析为JSON
        if isinstance(add_headers, str):
            try:
                add_headers = json.loads(add_headers)
            except (json.JSONDecodeError, TypeError):
                add_headers = {}
        
        if add_headers:
            processed_headers.update(add_headers)
        
        # 确保必要的请求头
        if 'user-agent' not in processed_headers:
            processed_headers['user-agent'] = f"M-FastGate/{settings.app['version']}"
        
        return processed_headers
    
    def _process_request_body(self, body: Dict[str, Any], route_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理请求体
        
        Args:
            body: 原始请求体
            route_config: 路由配置
            
        Returns:
            Dict[str, Any]: 处理后的请求体
        """
        if not body:
            return body
            
        processed_body = body.copy()
        
        # 添加字段
        add_body_fields = route_config.get('add_body_fields', {})
        
        # 如果add_body_fields是字符串，尝试解析为JSON
        if isinstance(add_body_fields, str):
            try:
                add_body_fields = json.loads(add_body_fields)
            except (json.JSONDecodeError, TypeError):
                add_body_fields = {}
        
        if add_body_fields:
            processed_body.update(add_body_fields)
        
        return processed_body
    
    def _process_response_headers(self, headers: Dict[str, str]) -> Dict[str, str]:
        """
        处理响应头 - 强制流式无缓冲
        
        Args:
            headers: 原始响应头
            
        Returns:
            Dict[str, str]: 处理后的响应头
        """
        processed_headers = {}
        
        # 对于流式响应，需要特殊处理
        content_type = headers.get("content-type", "").lower()
        is_stream = ("text/event-stream" in content_type or 
                    "application/x-ndjson" in content_type)
        
        # 保留重要的响应头
        important_headers = [
            'content-type', 'content-encoding',
            'cache-control', 'etag', 'last-modified',
            'access-control-allow-origin', 'access-control-allow-methods',
            'access-control-allow-headers', 'access-control-expose-headers'
        ]
        
        # 对于流式响应，不传递content-length
        if not is_stream:
            important_headers.append('content-length')
        
        for key, value in headers.items():
            if key.lower() in important_headers:
                processed_headers[key] = value
        
        # 添加代理标识
        processed_headers['x-proxied-by'] = f"M-FastGate/{settings.app['version']}"
        
        # 对于流式响应，添加强制无缓冲头
        if is_stream:
            # 核心无缓冲指令
            processed_headers['cache-control'] = 'no-cache, no-store, must-revalidate'
            processed_headers['pragma'] = 'no-cache'
            processed_headers['expires'] = '0'
            processed_headers['connection'] = 'keep-alive'
            
            # 禁用各种代理和服务器的缓冲
            processed_headers['x-accel-buffering'] = 'no'  # nginx
            processed_headers['x-nginx-proxy'] = 'no-buffer'  # nginx代理
            processed_headers['x-proxy-buffering'] = 'no'  # 通用代理
            processed_headers['x-buffer'] = 'no'  # 其他缓冲
            
            # FastAPI/Uvicorn 流式响应优化
            processed_headers['transfer-encoding'] = 'chunked'
        
        return processed_headers
    
    async def close(self):
        """关闭HTTP客户端"""
        await self.client.aclose()
        self.logger.info("Proxy engine client closed")
    
    def is_stream_response(self, response: httpx.Response) -> bool:
        """
        判断是否为流式响应
        
        Args:
            response: 响应对象
            
        Returns:
            bool: 是否为流式响应
        """
        content_type = response.headers.get("content-type", "").lower()
        return (
            "text/event-stream" in content_type or
            "application/x-ndjson" in content_type or
            "text/plain" in content_type and "stream" in content_type
        )
    
    def build_target_url(self, route_config: Dict[str, Any], original_path: str) -> str:
        """
        构建目标URL
        
        Args:
            route_config: 路由配置
            original_path: 原始请求路径
            
        Returns:
            str: 构建的目标URL
        """
        protocol = route_config.get('target_protocol', 'http')
        host = route_config['target_host']
        target_path = route_config['target_path']
        
        # 处理路径前缀剔除
        if route_config.get('strip_path_prefix', False):
            match_path = route_config['match_path'].rstrip('/*')
            if original_path.startswith(match_path):
                remaining_path = original_path[len(match_path):].lstrip('/')
                if remaining_path:
                    target_path = f"{target_path.rstrip('/')}/{remaining_path}"
        
        # 构建完整URL
        return f"{protocol}://{host}{target_path}"
    
    async def raw_stream_response(self, response: httpx.Response) -> httpx.Response:
        """
        直接返回原始流式响应 - 绕过FastAPI包装
        
        Args:
            response: 原始响应对象
            
        Returns:
            httpx.Response: 原始响应对象
        """
        self.logger.info(
            "Returning raw stream response",
            status_code=response.status_code,
            content_type=response.headers.get("content-type", "")
        )
        return response
    
    async def forward_stream_request(
        self,
        route_config: Dict[str, Any],
        method: str,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
        content: Optional[bytes] = None,
        audit_service=None,
        request_id: str = None,
        **kwargs
    ) -> StreamingResponse:
        """
        专门处理流式请求 - 带审计缓存的正确实现
        
        Args:
            route_config: 路由配置
            method: HTTP方法
            url: 目标URL
            headers: 请求头
            params: 查询参数
            json: JSON请求体
            content: 原始请求体
            audit_service: 审计服务（可选）
            request_id: 请求ID（可选）
            **kwargs: 其他请求参数
            
        Returns:
            StreamingResponse: FastAPI流式响应
        """
        timeout = route_config.get('timeout', settings.proxy.get('timeout', 30))
        
        # 处理请求头
        processed_headers = self._process_headers(headers or {}, route_config)
        
        self.logger.info(
            "Starting stream request with audit cache",
            method=method,
            url=url,
            request_id=request_id
        )
        
        async def stream_wrapper() -> AsyncGenerator[bytes, None]:
            """流式响应包装器 - 审计缓存+chunk合并模式"""
            import time
            import json as json_module  # 重命名避免与参数json冲突
            from datetime import datetime
            
            # 审计缓存变量（仅内存操作，不阻塞）
            start_time = time.time()
            first_chunk_time = None
            chunk_count = 0
            total_size = 0
            response_status = None
            response_headers = None
            
            # OpenAI chunk收集和合并变量
            collected_chunks = []  # 收集所有chunk数据
            merged_content = ""    # 合并后的完整content
            completion_info = {}   # 完整的completion信息
            
            try:
                # 调试日志：记录改造后的流式请求头和请求体
                processed_json = self._process_request_body(json, route_config) if json is not None else None
                self.logger.debug(
                    "Proxy stream request details",
                    method=method,
                    url=url,
                    processed_headers=processed_headers,
                    processed_body=processed_json,
                    content_length=len(str(content)) if content else 0,
                    request_id=request_id
                )
                
                # 关键：直接在async with中使用client.stream()
                async with self.client.stream(
                    method=method,
                    url=url,
                    headers=processed_headers,
                    timeout=timeout,
                    params=params,
                    json=processed_json,
                    content=content
                ) as response:
                    response.raise_for_status()
                    
                    # 缓存响应信息（仅内存操作）
                    response_status = response.status_code
                    response_headers = dict(response.headers)
                    
                    self.logger.info(
                        "Stream response started",
                        status_code=response.status_code,
                        content_type=response.headers.get("content-type", ""),
                        request_id=request_id
                    )
                    
                    # 直接迭代字节流
                    async for chunk in response.aiter_bytes(chunk_size=1024):
                        if chunk:
                            # 记录首个chunk时间（仅内存操作）
                            if first_chunk_time is None:
                                first_chunk_time = datetime.now()
                                end_time = time.time()
                                self.logger.info(f"First chunk received in: {end_time - start_time:.3f}s")
                            
                            # 更新缓存计数（仅内存操作）
                            chunk_count += 1
                            total_size += len(chunk)
                            
                            # 收集chunk用于后续合并（仅内存操作）
                            chunk_text = chunk.decode('utf-8', errors='ignore')
                            collected_chunks.append(chunk_text)
                            
                            # 立即yield，绝对无阻塞
                            yield chunk
                            
            except Exception as e:
                self.logger.error("Stream request error", error=str(e), request_id=request_id)
                # 即使出错也要记录审计信息
                if audit_service and request_id:
                    import asyncio
                    end_time = datetime.now()
                    asyncio.create_task(audit_service.log_request_complete(request_id, {
                        "status_code": response_status or 500,
                        "response_time": end_time,
                        "first_response_time": first_chunk_time,
                        "is_stream": True,
                        "stream_chunks": chunk_count,
                        "response_headers": response_headers,
                        "response_body": None,
                        "response_size": total_size,
                        "error_message": str(e)
                    }))
                raise
            finally:
                # 流式传输完成后，进行chunk合并和审计记录
                if audit_service and request_id:
                    import asyncio
                    end_time = datetime.now()
                    
                    # OpenAI格式chunk合并处理
                    merged_response = self._merge_openai_chunks(collected_chunks)
                    
                    self.logger.info(
                        "Stream completed - merged response ready",
                        chunk_count=chunk_count,
                        total_size=total_size,
                        merged_content_length=len(merged_response.get("content", "")),
                        request_id=request_id
                    )
                    
                    # 异步记录完整的审计信息，包含合并后的响应体
                    asyncio.create_task(audit_service.log_request_complete(request_id, {
                        "status_code": response_status,
                        "response_time": end_time,
                        "first_response_time": first_chunk_time,
                        "is_stream": True,
                        "stream_chunks": chunk_count,
                        "response_headers": response_headers,
                        "response_body": merged_response,  # 合并后的完整响应体
                        "response_size": total_size
                    }))
                    
                    # 如果需要记录首次响应时间
                    if first_chunk_time:
                        asyncio.create_task(audit_service.log_first_response(request_id, first_chunk_time))
        
        # 优化响应头，强制无缓冲  
        response_headers = self._process_response_headers({
            "content-type": "text/event-stream",
            "cache-control": "no-cache",
            "connection": "keep-alive"
        })
        
        return StreamingResponse(
            stream_wrapper(),
            media_type="text/event-stream",
            headers=response_headers
        )
    
    def _merge_openai_chunks(self, collected_chunks: List[str]) -> Dict[str, Any]:
        """
        合并OpenAI格式的流式响应chunks
        
        Args:
            collected_chunks: 收集的所有chunk文本列表
            
        Returns:
            Dict[str, Any]: 合并后的完整响应信息
        """
        import json
        import re
        
        merged_content = ""
        completion_info = {
            "id": "",
            "object": "chat.completion",
            "created": 0,
            "model": "",
            "choices": [],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        }
        
        try:
            # 合并所有chunk文本
            full_text = "".join(collected_chunks)
            
            # 按行分割，每个data行是一个chunk
            lines = full_text.split('\n')
            
            content_parts = []
            role = None
            finish_reason = None
            
            for line in lines:
                line = line.strip()
                
                # 跳过空行和非data行
                if not line or not line.startswith('data: '):
                    continue
                    
                # 跳过[DONE]标记
                if line == 'data: [DONE]':
                    continue
                
                try:
                    # 提取JSON部分
                    json_str = line[6:]  # 去掉 'data: ' 前缀
                    chunk_data = json.loads(json_str)
                    
                    # 提取基础信息（从第一个有效chunk）
                    if not completion_info["id"] and "id" in chunk_data:
                        completion_info["id"] = chunk_data.get("id", "")
                        completion_info["created"] = chunk_data.get("created", 0)
                        completion_info["model"] = chunk_data.get("model", "")
                    
                    # 处理choices
                    if "choices" in chunk_data and chunk_data["choices"]:
                        choice = chunk_data["choices"][0]
                        delta = choice.get("delta", {})
                        
                        # 提取role（通常在第一个chunk）
                        if "role" in delta and not role:
                            role = delta["role"]
                        
                        # 提取content
                        if "content" in delta:
                            content_parts.append(delta["content"])
                        
                        # 提取finish_reason（通常在最后一个chunk）
                        if choice.get("finish_reason"):
                            finish_reason = choice["finish_reason"]
                            
                except json.JSONDecodeError as e:
                    self.logger.warning(f"Failed to parse chunk JSON: {e}")
                    continue
            
            # 合并所有content部分
            merged_content = "".join(content_parts)
            
            # 构建完整的响应格式
            completion_info["choices"] = [{
                "index": 0,
                "message": {
                    "role": role or "assistant",
                    "content": merged_content
                },
                "finish_reason": finish_reason or "stop"
            }]
            
            # 简单估算token数量（实际应该用tokenizer）
            estimated_completion_tokens = len(merged_content.split())
            completion_info["usage"]["completion_tokens"] = estimated_completion_tokens
            completion_info["usage"]["total_tokens"] = estimated_completion_tokens
            
            self.logger.info(
                "Chunks merged successfully",
                chunks_processed=len([l for l in full_text.split('\n') if l.strip().startswith('data: ')]),
                content_length=len(merged_content),
                estimated_tokens=estimated_completion_tokens
            )
            
            return {
                "content": merged_content,
                "full_response": completion_info,
                "role": role or "assistant",
                "finish_reason": finish_reason or "stop"
            }
            
        except Exception as e:
            self.logger.error(f"Error merging chunks: {e}")
            return {
                "content": "",
                "full_response": completion_info,
                "role": "assistant",
                "finish_reason": "error",
                "error": str(e)
            } 