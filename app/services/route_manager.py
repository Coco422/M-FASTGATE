"""
路由管理和代理转发服务
"""

import asyncio
import time
from typing import Optional, Dict, Any
from fastapi import HTTPException, status, Request
import httpx
from ..config import routes_config, RouteConfig
from ..models.audit_log import generate_request_id


class RouteManager:
    """路由管理器"""
    
    def __init__(self):
        self.routes = routes_config
        self.client = httpx.AsyncClient(timeout=30.0)
    
    async def find_route(self, path: str) -> Optional[RouteConfig]:
        """
        根据路径查找匹配的路由配置
        
        Args:
            path: 请求路径
            
        Returns:
            RouteConfig: 匹配的路由配置，未找到返回None
        """
        for route in self.routes:
            if path.startswith(route.path_prefix):
                return route
        return None
    
    async def proxy_request(
        self,
        request: Request,
        route: RouteConfig,
        request_id: str = None
    ) -> Dict[str, Any]:
        """
        代理转发请求
        
        Args:
            request: 原始请求
            route: 路由配置
            request_id: 请求ID
            
        Returns:
            Dict: 包含响应数据和元信息的字典
            
        Raises:
            HTTPException: 转发失败时抛出异常
        """
        if not request_id:
            request_id = generate_request_id()
        
        start_time = time.time()
        
        # 选择目标服务器（简单轮询，Phase 1不实现复杂负载均衡）
        target = route.targets[0] if route.targets else None
        if not target:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="No available target servers"
            )
        
        # 构建目标URL
        path = str(request.url.path)
        target_path = path[len(route.path_prefix):] if path.startswith(route.path_prefix) else path
        target_url = f"{target.url.rstrip('/')}{target_path}"
        
        if request.url.query:
            target_url += f"?{request.url.query}"
        
        # 准备请求头
        headers = dict(request.headers)
        # 移除可能导致问题的头
        headers.pop("host", None)
        headers.pop("content-length", None)
        
        try:
            # 读取请求体
            body = await request.body()
            
            # 发送代理请求
            response = await self.client.request(
                method=request.method,
                url=target_url,
                headers=headers,
                content=body,
                timeout=target.timeout
            )
            
            end_time = time.time()
            response_time_ms = int((end_time - start_time) * 1000)
            
            return {
                "status_code": response.status_code,
                "headers": dict(response.headers),
                "content": response.content,
                "response_time_ms": response_time_ms,
                "target_url": target_url,
                "request_size": len(body),
                "response_size": len(response.content)
            }
            
        except httpx.TimeoutException:
            response_time_ms = int((time.time() - start_time) * 1000)
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail=f"Request timeout after {target.timeout}s"
            )
        except httpx.ConnectError:
            response_time_ms = int((time.time() - start_time) * 1000)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Cannot connect to target server: {target.url}"
            )
        except Exception as e:
            response_time_ms = int((time.time() - start_time) * 1000)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Proxy error: {str(e)}"
            )
    
    async def close(self):
        """关闭HTTP客户端"""
        await self.client.aclose()


# 全局路由管理器实例
route_manager = RouteManager() 