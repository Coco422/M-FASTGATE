"""
API网关服务 - 专门处理 /proxy/miniai/v2/chat/completions 请求
"""

import json
import time
import asyncio
from typing import Dict, Any, Optional
from fastapi import Request, HTTPException, status
from fastapi.responses import StreamingResponse
import httpx

from ..config import settings
from ..models.audit_log import AuditLogCreate, generate_request_id
from ..models.api_key import APIKeyResponse


class APIGatewayService:
    """API网关服务"""
    
    def __init__(self):
        self.backend_url = settings.api_gateway.backend_url
        self.backend_path = settings.api_gateway.backend_path
        self.real_api_key = settings.api_gateway.real_api_key
        self.timeout = settings.api_gateway.timeout
        self.strip_headers = settings.api_gateway.strip_headers
        self.strip_body_fields = settings.api_gateway.strip_body_fields
        
        # HTTP客户端
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(self.timeout, read=300.0)
        )
    
    async def process_chat_completions(
        self,
        request: Request,
        api_key_info: APIKeyResponse,
        audit_service,
        client_ip: str,
        user_agent: str,
        source_path: Optional[str] = None
    ) -> StreamingResponse:
        """
        处理聊天完成请求
        
        Args:
            request: 原始请求
            api_key_info: API Key信息
            audit_service: 审计服务
            client_ip: 客户端IP
            user_agent: 用户代理
            source_path: 来源路径
        
        Returns:
            StreamingResponse: 流式响应或普通响应
        """
        start_time = time.time()
        request_id = generate_request_id()
        
        # 读取原始请求体
        original_body = await request.body()
        
        # 清洗请求参数
        cleaned_headers, cleaned_body = await self._clean_request_params(
            dict(request.headers), original_body
        )
        
        # 构建后端请求URL
        backend_url = f"{self.backend_url}{self.backend_path}"
        
        # 添加查询参数
        if request.url.query:
            backend_url += f"?{request.url.query}"
        
        try:
            # 检查是否为流式请求
            is_stream_request = await self._is_stream_request(original_body)
            
            if is_stream_request:
                # 处理流式请求
                return await self._handle_stream_request(
                    request,
                    backend_url, cleaned_headers, cleaned_body,
                    request_id, api_key_info, audit_service,
                    client_ip, user_agent, source_path, start_time
                )
            else:
                # 处理普通请求
                return await self._handle_normal_request(
                    request,
                    backend_url, cleaned_headers, cleaned_body,
                    request_id, api_key_info, audit_service,
                    client_ip, user_agent, source_path, start_time
                )
                
        except Exception as e:
            # 异步记录错误审计日志
            if settings.api_gateway.async_audit:
                asyncio.create_task(self._async_log_error(
                    audit_service, request_id, api_key_info, 
                    request, client_ip, user_agent, source_path, 
                    start_time, str(e)
                ))
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Gateway error: {str(e)}"
            )
    
    async def _clean_request_params(
        self, 
        headers: Dict[str, str], 
        body: bytes
    ) -> tuple[Dict[str, str], bytes]:
        """
        清洗请求参数
        
        Args:
            headers: 原始请求头
            body: 原始请求体
        
        Returns:
            tuple: (清洗后的请求头, 清洗后的请求体)
        """
        # 清洗请求头
        cleaned_headers = {}
        for key, value in headers.items():
            if key.lower() not in [h.lower() for h in self.strip_headers]:
                cleaned_headers[key] = value
        
        # 添加真实API Key
        cleaned_headers["Authorization"] = f"Bearer {self.real_api_key}"
        cleaned_headers["Content-Type"] = "application/json"
        
        # 清洗请求体
        cleaned_body = body
        if self.strip_body_fields and body:
            try:
                body_data = json.loads(body)
                for field in self.strip_body_fields:
                    body_data.pop(field, None)
                cleaned_body = json.dumps(body_data).encode()
            except:
                # 如果不是JSON格式，保持原样
                pass
        
        return cleaned_headers, cleaned_body
    
    async def _is_stream_request(self, body: bytes) -> bool:
        """检查是否为流式请求"""
        try:
            data = json.loads(body)
            return data.get("stream", False)
        except:
            return False
    
    async def _handle_stream_request(
        self,
        request: Request,  # 添加这个参数
        backend_url: str,
        headers: Dict[str, str],
        body: bytes,
        request_id: str,
        api_key_info: APIKeyResponse,
        audit_service,
        client_ip: str,
        user_agent: str,
        source_path: Optional[str],
        start_time: float
    ) -> StreamingResponse:
        """处理流式请求"""
        
        async def stream_generator():
            chunks_count = 0
            total_response_size = 0
            response_status = 200
            response_headers_dict = {}
            collected_content = b""  # 收集响应内容
            max_content_size = 1000000  # 最大收集1000KB的响应内容
            
            try:
                async with self.client.stream(
                    "POST",
                    backend_url,
                    headers=headers,
                    content=body
                ) as response:
                    response_status = response.status_code
                    response_headers_dict = dict(response.headers)
                    
                    async for chunk in response.aiter_bytes():
                        chunks_count += 1
                        total_response_size += len(chunk)
                        
                        # 收集部分响应内容用于日志记录
                        if len(collected_content) < max_content_size:
                            remaining_space = max_content_size - len(collected_content)
                            collected_content += chunk[:remaining_space]
                        
                        yield chunk
            
            except Exception as e:
                response_status = 502
                error_chunk = f"data: {{\"error\": \"{str(e)}\"}}\n\n"
                error_bytes = error_chunk.encode()
                collected_content = error_bytes
                yield error_bytes
            
            finally:
                # 异步记录增强审计日志
                if settings.api_gateway.async_audit:
                    asyncio.create_task(self._async_log_request(
                        audit_service, request, request_id, api_key_info,
                        backend_url, response_status, time.time() - start_time,
                        response_content=collected_content,
                        response_headers=response_headers_dict,
                        source_path=source_path, is_stream=True,
                        chunks_count=chunks_count
                    ))
        
        return StreamingResponse(
            stream_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*"
            }
        )
    
    async def _handle_normal_request(
        self,
        request: Request,  # 添加这个参数
        backend_url: str,
        headers: Dict[str, str],
        body: bytes,
        request_id: str,
        api_key_info: APIKeyResponse,
        audit_service,
        client_ip: str,
        user_agent: str,
        source_path: Optional[str],
        start_time: float
    ) -> Dict[str, Any]:
        """处理普通请求"""
        
        response = await self.client.post(
            backend_url,
            headers=headers,
            content=body
        )
        
        end_time = time.time()
        response_time = end_time - start_time
        
        # 异步记录审计日志
        if settings.api_gateway.async_audit:
            asyncio.create_task(self._async_log_request(
                audit_service, request, request_id, api_key_info,
                backend_url, response.status_code, response_time,
                response_content=response.content,
                response_headers=dict(response.headers),
                source_path=source_path, is_stream=False
            ))
        
        return {
            "status_code": response.status_code,
            "headers": dict(response.headers),
            "content": response.content
        }
    
    async def _async_log_request(
        self,
        audit_service,
        request: Request,
        request_id: str,
        api_key_info: APIKeyResponse,
        backend_url: str,
        status_code: int,
        response_time: float,
        response_content: bytes = None,
        response_headers: Dict[str, str] = None,
        source_path: Optional[str] = None,
        is_stream: bool = False,
        chunks_count: int = 0,
        error_message: str = None
    ):
        """异步记录审计日志"""
        try:
            await audit_service.create_enhanced_log(
                request=request,
                request_id=request_id,
                api_key=api_key_info.key_value,
                source_path=source_path or api_key_info.source_path,
                target_url=backend_url,
                status_code=status_code,
                response_time_ms=int(response_time * 1000),
                response_content=response_content,
                response_headers=response_headers,
                is_stream=is_stream,
                stream_chunks=chunks_count,
                error_message=error_message
            )
        except Exception as e:
            # 审计日志失败不应该影响业务请求
            print(f"Failed to create audit log: {e}")
    
    
    async def close(self):
        """关闭HTTP客户端"""
        await self.client.aclose()


# 全局API网关服务实例
api_gateway_service = APIGatewayService() 