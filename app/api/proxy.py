"""
M-FastGate v0.2.0 统一代理接口
"""

import time
from datetime import datetime
from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import StreamingResponse, Response
from sqlalchemy.orm import Session
from ..database import get_db
from ..middleware.auth import api_key_auth, get_source_path, get_client_ip
from ..services.proxy_engine import ProxyEngine
from ..services.route_matcher import RouteMatcher
from ..services.audit_service import AuditService
from ..models.api_key import APIKeyResponse
from ..models.audit_log import generate_request_id
from ..config import settings

router = APIRouter()


@router.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"])
async def universal_proxy(
    path: str,
    request: Request,
    db: Session = Depends(get_db),
    api_key_info: APIKeyResponse = Depends(api_key_auth)
):
    """
    统一代理接口 - v0.2.0核心功能
    
    支持：
    - 路径匹配和前缀剥离
    - 请求体内容匹配
    - 请求头和请求体转换
    - 流式和非流式响应
    - 完整的审计日志
    
    Args:
        path: 请求路径
        request: FastAPI请求对象  
        db: 数据库会话
        api_key_info: API密钥信息
        
    Returns:
        Response: 代理响应或错误响应
    """
    start_time = time.time()
    request_id = generate_request_id()
    
    # 获取请求元信息
    source_path = get_source_path(request)
    client_ip = get_client_ip(request)
    request_path = f"/{path}"
    
    # 初始化服务
    route_matcher = RouteMatcher()
    proxy_engine = ProxyEngine()
    audit_service = AuditService()
    
    try:
        # 获取请求体（如果存在）
        request_body = None
        if request.method in ["POST", "PUT", "PATCH"]:
            content_type = request.headers.get("content-type", "")
            if "application/json" in content_type:
                request_body = await request.json()
            elif content_type:
                # 其他类型的请求体，读取为bytes
                request_body = await request.body()
        
        # 获取所有活跃的代理路由
        from ..models.proxy_route import ProxyRouteDB
        routes = db.query(ProxyRouteDB).filter(ProxyRouteDB.is_active == True).all()
        
        # 转换为字典格式
        route_dicts = []
        for route in routes:
            route_dict = {
                "route_id": route.route_id,
                "route_name": route.route_name,
                "description": route.description,
                "match_path": route.match_path,
                "match_method": route.match_method,
                "match_headers": route.match_headers,
                "match_body_schema": route.match_body_schema,
                "target_host": route.target_host,
                "target_path": route.target_path,
                "target_protocol": route.target_protocol,
                "strip_path_prefix": route.strip_path_prefix,
                "add_headers": route.add_headers,
                "add_body_fields": route.add_body_fields,
                "remove_headers": route.remove_headers,
                "timeout": route.timeout,
                "retry_count": route.retry_count,
                "is_active": route.is_active,
                "priority": route.priority
            }
            route_dicts.append(route_dict)
        
        # 构建请求信息
        request_info = {
            "path": request_path,
            "method": request.method,
            "headers": dict(request.headers),
            "body": request_body if isinstance(request_body, dict) else {}
        }
        
        # 路由匹配
        route_match = route_matcher.find_matching_route(request_info, route_dicts)
        
        if not route_match:
            # 记录未匹配的审计日志
            await audit_service.log_request_start({
                "request_id": request_id,
                "api_key": api_key_info.key_value,
                "path": request_path,
                "method": request.method,
                "ip_address": client_ip,
                "request_time": datetime.fromtimestamp(start_time),
                "user_agent": request.headers.get("user-agent", ""),
                "request_headers": dict(request.headers),
                "request_body": request_body if isinstance(request_body, dict) else None
            })
            
            await audit_service.log_request_complete(request_id, {
                "status_code": 404,
                "response_time": datetime.now(),
                "error_message": "No matching route found"
            })
            
            raise HTTPException(
                status_code=404,
                detail="No matching route configuration found"
            )
        
        # 构建目标URL
        target_url = proxy_engine.build_target_url(route_match, request_path)
        
        # 代理请求执行
        response = await proxy_engine.forward_request(
            route_config=route_match,
            method=request.method,
            url=target_url,
            headers=dict(request.headers),
            json=request_body if isinstance(request_body, dict) else None,
            content=request_body if isinstance(request_body, bytes) else None
        )
        
        # 计算总响应时间
        end_time = time.time()
        total_response_time = int((end_time - start_time) * 1000)
        
        # 检查是否为流式响应
        is_stream = proxy_engine.is_stream_response(response)
        
        # 记录请求开始
        await audit_service.log_request_start({
            "request_id": request_id,
            "api_key": api_key_info.key_value,
            "path": request_path,
            "method": request.method,
            "ip_address": client_ip,
            "target_url": target_url,
            "request_time": datetime.fromtimestamp(start_time),
            "user_agent": request.headers.get("user-agent", ""),
            "request_headers": dict(request.headers),
            "request_body": request_body if isinstance(request_body, dict) else None,
            "request_size": len(str(request_body)) if request_body else 0
        })
        
        # 记录请求完成
        response_content = None if is_stream else await response.aread()
        await audit_service.log_request_complete(request_id, {
            "status_code": response.status_code,
            "response_time": datetime.now(),
            "is_stream": is_stream,
            "response_headers": dict(response.headers),
            "response_body": response_content,
            "response_size": len(response_content) if response_content else 0
        })
        
        # 返回响应
        if is_stream:
            return await proxy_engine.handle_stream_response(response)
        else:
            # 处理响应头
            processed_headers = proxy_engine._process_response_headers(dict(response.headers))
            
            return Response(
                content=response_content,
                status_code=response.status_code,
                headers=processed_headers,
                media_type=response.headers.get("content-type", "application/json")
            )
            
    except HTTPException:
        # 重新抛出HTTP异常
        raise
        
    except Exception as e:
        # 记录错误的审计日志
        end_time = time.time()
        
        await audit_service.log_request_start({
            "request_id": request_id,
            "api_key": api_key_info.key_value,
            "path": request_path,
            "method": request.method,
            "ip_address": client_ip,
            "request_time": datetime.fromtimestamp(start_time),
            "user_agent": request.headers.get("user-agent", ""),
            "request_headers": dict(request.headers),
            "request_body": request_body if isinstance(request_body, dict) else None
        })
        
        await audit_service.log_request_complete(request_id, {
            "status_code": 500,
            "response_time": datetime.fromtimestamp(end_time),
            "error_message": str(e)
        })
        
        raise HTTPException(
            status_code=500,
            detail="Internal proxy error"
        ) 