"""
动态路由管理服务
"""

import re
import time
import asyncio
from typing import Optional, List, Dict, Any
from urllib.parse import urlparse, unquote
from sqlalchemy.orm import Session
from fastapi import HTTPException, status, Request
from fastapi.responses import StreamingResponse
import httpx

from ..models.route_config import (
    RouteConfigDB, RouteConfigCreate, RouteConfigUpdate, 
    RouteConfigResponse, generate_route_id
)


class DynamicRouteManager:
    """动态路由管理器"""
    
    def __init__(self, db: Session):
        self.db = db
        self.client = httpx.AsyncClient(timeout=httpx.Timeout(30.0, read=300.0))
        # 缓存活跃路由配置
        self._route_cache = {}
        self._load_routes()
    
    def _load_routes(self):
        """从数据库加载路由配置到缓存"""
        routes = self.db.query(RouteConfigDB).filter(RouteConfigDB.is_active == True).all()
        self._route_cache = {route.route_id: route for route in routes}
    
    def _to_response(self, db_route: RouteConfigDB) -> RouteConfigResponse:
        """转换数据库模型到响应模型"""
        return RouteConfigResponse(
            route_id=db_route.route_id,
            name=db_route.name,
            description=db_route.description,
            target_url=db_route.target_url,
            path_prefix=db_route.path_prefix,
            is_active=db_route.is_active,
            timeout=db_route.timeout,
            created_at=db_route.created_at,
            updated_at=db_route.updated_at
        )
    
    def create_route(self, route_data: RouteConfigCreate) -> RouteConfigResponse:
        """创建新的路由配置"""
        # 验证目标URL格式
        if not self._is_valid_url(route_data.target_url):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid target URL format"
            )
        
        # 生成路由ID
        route_id = generate_route_id()
        
        # 创建数据库记录
        db_route = RouteConfigDB(
            route_id=route_id,
            name=route_data.name,
            description=route_data.description,
            target_url=route_data.target_url,
            path_prefix=route_data.path_prefix,
            is_active=route_data.is_active,
            timeout=route_data.timeout
        )
        
        self.db.add(db_route)
        self.db.commit()
        self.db.refresh(db_route)
        
        # 更新缓存
        if db_route.is_active:
            self._route_cache[route_id] = db_route
        
        return self._to_response(db_route)
    
    def get_routes(self) -> List[RouteConfigResponse]:
        """获取所有路由配置"""
        routes = self.db.query(RouteConfigDB).order_by(RouteConfigDB.created_at.desc()).all()
        return [self._to_response(route) for route in routes]
    
    def get_route(self, route_id: str) -> Optional[RouteConfigResponse]:
        """获取单个路由配置"""
        db_route = self.db.query(RouteConfigDB).filter(RouteConfigDB.route_id == route_id).first()
        return self._to_response(db_route) if db_route else None
    
    def update_route(self, route_id: str, route_data: RouteConfigUpdate) -> Optional[RouteConfigResponse]:
        """更新路由配置"""
        db_route = self.db.query(RouteConfigDB).filter(RouteConfigDB.route_id == route_id).first()
        if not db_route:
            return None
        
        # 更新字段
        update_data = route_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            if hasattr(db_route, field):
                setattr(db_route, field, value)
        
        # 验证目标URL
        if route_data.target_url and not self._is_valid_url(route_data.target_url):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid target URL format"
            )
        
        self.db.commit()
        self.db.refresh(db_route)
        
        # 更新缓存
        if db_route.is_active:
            self._route_cache[route_id] = db_route
        else:
            self._route_cache.pop(route_id, None)
        
        return self._to_response(db_route)
    
    def delete_route(self, route_id: str) -> bool:
        """删除路由配置"""
        db_route = self.db.query(RouteConfigDB).filter(RouteConfigDB.route_id == route_id).first()
        if not db_route:
            return False
        
        self.db.delete(db_route)
        self.db.commit()
        
        # 从缓存中移除
        self._route_cache.pop(route_id, None)
        
        return True
    
    def _is_valid_url(self, url: str) -> bool:
        """验证URL格式"""
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc])
        except:
            return False
    
    def _is_safe_url(self, url: str) -> bool:
        """检查URL安全性，防止SSRF攻击"""
        try:
            parsed = urlparse(url)
            
            # 不允许访问内网地址（简单检查）
            if parsed.hostname:
                # 禁止localhost和127.0.0.1
                if parsed.hostname.lower() in ['localhost', '127.0.0.1']:
                    return False
                # 禁止内网IP段（简单检查）
                if parsed.hostname.startswith('192.168.') or parsed.hostname.startswith('10.'):
                    return False
            
            return True
        except:
            return False
    
    async def proxy_dynamic_request(
        self, 
        target_url: str, 
        request: Request,
        request_id: str = None
    ) -> Dict[str, Any]:
        """
        代理动态请求到目标URL
        
        Args:
            target_url: 目标URL
            request: 原始请求
            request_id: 请求ID
            
        Returns:
            Dict: 包含响应数据的字典
        """
        # URL解码
        target_url = unquote(target_url)
        
        # 验证URL安全性（在生产环境中启用）
        # if not self._is_safe_url(target_url):
        #     raise HTTPException(
        #         status_code=status.HTTP_403_FORBIDDEN,
        #         detail="Access to this URL is forbidden"
        #     )
        
        if not self._is_valid_url(target_url):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid target URL"
            )
        
        start_time = time.time()
        
        # 添加查询参数
        if request.url.query:
            separator = "&" if "?" in target_url else "?"
            target_url = f"{target_url}{separator}{request.url.query}"
        
        # 准备请求头
        headers = dict(request.headers)
        # 移除可能导致问题的头
        headers.pop("host", None)
        headers.pop("content-length", None)
        
        try:
            # 读取请求体
            body = await request.body()
            
            # 检查是否是流式请求
            is_stream = (
                "text/event-stream" in headers.get("accept", "") or
                "application/x-ndjson" in headers.get("accept", "") or
                request.headers.get("cache-control") == "no-cache"
            )
            
            if is_stream:
                # 处理流式响应
                return await self._handle_stream_response(
                    target_url, request.method, headers, body, start_time
                )
            else:
                # 处理普通响应
                response = await self.client.request(
                    method=request.method,
                    url=target_url,
                    headers=headers,
                    content=body,
                    timeout=30.0
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
                    "response_size": len(response.content),
                    "is_stream": False
                }
                
        except httpx.TimeoutException:
            response_time_ms = int((time.time() - start_time) * 1000)
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail="Request timeout"
            )
        except httpx.ConnectError:
            response_time_ms = int((time.time() - start_time) * 1000)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Cannot connect to target server: {target_url}"
            )
        except Exception as e:
            response_time_ms = int((time.time() - start_time) * 1000)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Proxy error: {str(e)}"
            )
    
    async def _handle_stream_response(
        self, 
        target_url: str, 
        method: str, 
        headers: dict, 
        body: bytes,
        start_time: float
    ) -> Dict[str, Any]:
        """处理流式响应"""
        
        async def generate_stream():
            """生成流式响应"""
            chunks_count = 0
            total_size = 0
            
            try:
                async with self.client.stream(
                    method=method,
                    url=target_url,
                    headers=headers,
                    content=body,
                    timeout=httpx.Timeout(30.0, read=300.0)
                ) as response:
                    
                    # 先返回响应头信息
                    yield {
                        "type": "headers",
                        "status_code": response.status_code,
                        "headers": dict(response.headers)
                    }
                    
                    # 流式返回数据块
                    async for chunk in response.aiter_bytes():
                        chunks_count += 1
                        total_size += len(chunk)
                        yield {
                            "type": "chunk",
                            "data": chunk
                        }
            
            except Exception as e:
                yield {
                    "type": "error",
                    "error": str(e)
                }
            
            finally:
                end_time = time.time()
                response_time_ms = int((end_time - start_time) * 1000)
                yield {
                    "type": "summary",
                    "chunks_count": chunks_count,
                    "total_size": total_size,
                    "response_time_ms": response_time_ms,
                    "target_url": target_url
                }
        
        return {
            "is_stream": True,
            "stream_generator": generate_stream()
        }
    
    async def close(self):
        """关闭HTTP客户端"""
        await self.client.aclose() 