"""
通用代理转发引擎 - v0.2.0
实现HTTP/HTTPS协议转发、流式响应处理、错误处理和重试机制
"""

import asyncio
import httpx
import json
from typing import Dict, Any, Optional, AsyncGenerator
from fastapi import HTTPException
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
            **kwargs: 其他请求参数
            
        Returns:
            httpx.Response: 响应对象
            
        Raises:
            HTTPException: 转发失败时抛出
        """
        timeout = route_config.get('timeout', settings.proxy['timeout'])
        retry_count = route_config.get('retry_count', settings.proxy['max_retries'])
        
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
                self.logger.info(
                    "Forwarding request",
                    method=method,
                    url=url,
                    attempt=attempt + 1,
                    max_attempts=retry_count + 1
                )
                
                response = await self.client.request(**request_kwargs)
                
                self.logger.info(
                    "Request forwarded successfully",
                    status_code=response.status_code,
                    response_size=len(response.content) if hasattr(response, 'content') else 0
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
        处理流式响应
        
        Args:
            response: 原始响应对象
            audit_service: 审计服务实例（可选）
            request_id: 请求ID（可选）
            
        Returns:
            StreamingResponse: FastAPI流式响应
        """
        self.logger.info(
            "Handling stream response",
            status_code=response.status_code,
            content_type=response.headers.get("content-type", "")
        )
        
        async def stream_wrapper() -> AsyncGenerator[bytes, None]:
            """无缓冲流式响应包装器"""
            chunk_count = 0
            total_size = 0
            first_chunk_sent = False
            
            try:
                # 极小的chunk size以实现真正的实时流式
                chunk_size = 64  # 64字节，确保最小延迟
                
                async for chunk in response.aiter_bytes(chunk_size=chunk_size):
                    if not chunk:  # 跳过空chunk
                        continue
                        
                    chunk_count += 1
                    total_size += len(chunk)
                    
                    # 只在第一个chunk记录（完全异步，无等待）
                    if not first_chunk_sent and audit_service and request_id:
                        first_chunk_sent = True
                        import asyncio
                        from datetime import datetime
                        asyncio.create_task(audit_service.log_first_response(request_id, datetime.now()))
                    
                    # 立即yield，绝对不延迟
                    yield chunk
                    
                    # 仅偶尔记录统计（不影响主流程）
                    if audit_service and request_id and chunk_count % 50 == 0:
                        import asyncio
                        asyncio.create_task(audit_service.log_stream_chunk(request_id, len(chunk) * 50))
                    
                self.logger.info(
                    "Stream completed",
                    chunk_count=chunk_count,
                    total_size=total_size
                )
                
                # 异步记录完成（不等待）
                if audit_service and request_id:
                    import asyncio
                    from datetime import datetime
                    asyncio.create_task(audit_service.log_request_complete(request_id, {
                        "status_code": response.status_code,
                        "response_time": datetime.now(),
                        "is_stream": True,
                        "stream_chunks": chunk_count,
                        "response_headers": dict(response.headers),
                        "response_body": None,
                        "response_size": total_size
                    }))
                    
            except Exception as e:
                self.logger.error("Stream error", error=str(e))
                # 异步记录错误
                if audit_service and request_id:
                    import asyncio
                    from datetime import datetime
                    asyncio.create_task(audit_service.log_request_complete(request_id, {
                        "status_code": response.status_code,
                        "response_time": datetime.now(),
                        "is_stream": True,
                        "stream_chunks": chunk_count,
                        "response_headers": dict(response.headers),
                        "response_body": None,
                        "response_size": total_size,
                        "error_message": str(e)
                    }))
                raise
            finally:
                await response.aclose()
        
        # 优化响应头
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
        处理响应头
        
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
        
        # 对于流式响应，添加优化头
        if is_stream:
            processed_headers['cache-control'] = 'no-cache'
            processed_headers['connection'] = 'keep-alive'
            # 禁用nginx等的缓冲
            processed_headers['x-accel-buffering'] = 'no'
        
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