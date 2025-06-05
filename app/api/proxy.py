"""
代理接口
"""

import time
from fastapi import APIRouter, Request, HTTPException, status, Depends, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from ..database import get_db
from ..middleware.auth import api_key_auth, get_source_path, get_client_ip, get_user_agent
from ..services.route_manager import route_manager
from ..services.dynamic_route_manager import DynamicRouteManager
from ..services.audit_service import AuditService
from ..models.api_key import APIKeyResponse
from ..models.audit_log import AuditLogCreate, generate_request_id

router = APIRouter()


@router.api_route("/proxy/{target_url:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"])
async def proxy_dynamic_request(
    target_url: str,
    request: Request,
    db: Session = Depends(get_db),
    api_key_info: APIKeyResponse = Depends(api_key_auth)
):
    """
    动态代理转发接口
    支持 /proxy/{target_url} 格式的动态转发
    
    示例: POST /proxy/http://172.16.99.32:1030/miniai/v2/chat/completions
    """
    start_time = time.time()
    request_id = generate_request_id()
    
    # 获取请求元信息
    source_path = get_source_path(request)
    client_ip = get_client_ip(request)
    user_agent = get_user_agent(request)
    request_path = f"/proxy/{target_url}"
    
    # 创建动态路由管理器
    dynamic_route_manager = DynamicRouteManager(db)
    
    try:
        # 执行动态代理转发
        proxy_result = await dynamic_route_manager.proxy_dynamic_request(
            target_url, request, request_id
        )
        
        # 处理流式响应
        if proxy_result.get("is_stream"):
            async def stream_wrapper():
                async for item in proxy_result["stream_generator"]:
                    if item["type"] == "chunk":
                        yield item["data"]
            
            return StreamingResponse(
                stream_wrapper(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "Access-Control-Allow-Origin": "*"
                }
            )
        
        # 记录审计日志
        audit_service = AuditService(db)
        await audit_service.create_enhanced_log(
            request=request,
            request_id=request_id,
            api_key=api_key_info.key_value,
            source_path=source_path or api_key_info.source_path,
            target_url=proxy_result["target_url"],
            status_code=proxy_result["status_code"],
            response_time_ms=proxy_result["response_time_ms"],
            response_content=proxy_result["content"],
            response_headers=proxy_result["headers"]
        )
        
        # 构建响应
        response = Response(
            content=proxy_result["content"],
            status_code=proxy_result["status_code"],
            media_type=proxy_result["headers"].get("content-type", "application/octet-stream")
        )
        
        # 复制响应头
        excluded_headers = {
            "content-length", "content-encoding", "transfer-encoding", 
            "connection", "upgrade", "server"
        }
        for key, value in proxy_result["headers"].items():
            if key.lower() not in excluded_headers:
                response.headers[key] = value
        
        return response
        
    except HTTPException as e:
        # 记录失败的审计日志
        end_time = time.time()
        response_time_ms = int((end_time - start_time) * 1000)
        
        audit_service = AuditService(db)
        await audit_service.create_enhanced_log(
            request=request,
            request_id=request_id,
            api_key=api_key_info.key_value,
            source_path=source_path or api_key_info.source_path,
            target_url=proxy_result["target_url"],
            status_code=proxy_result["status_code"],
            response_time_ms=proxy_result["response_time_ms"],
            response_content=proxy_result["content"],
            response_headers=proxy_result["headers"]
        )
        
        raise e
    
    finally:
        # 关闭动态路由管理器
        await dynamic_route_manager.close()


@router.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"])
async def proxy_request(
    path: str,
    request: Request,
    db: Session = Depends(get_db),
    api_key_info: APIKeyResponse = Depends(api_key_auth)
):
    """
    通用代理转发接口
    
    Args:
        path: 请求路径
        request: FastAPI请求对象
        db: 数据库会话
        api_key_info: API Key信息
        
    Returns:
        Response: 代理响应
    """
    start_time = time.time()
    request_id = generate_request_id()
    
    # 获取请求元信息
    source_path = get_source_path(request)
    client_ip = get_client_ip(request)
    user_agent = get_user_agent(request)
    request_path = f"/{path}" if path else "/"
    
    # 查找匹配的路由
    route = await route_manager.find_route(request_path)
    if not route:
        # 记录404错误的审计日志
        audit_service = AuditService(db)
        await audit_service.create_enhanced_log(
            request=request,
            request_id=request_id,
            api_key=api_key_info.key_value if api_key_info else None,
            source_path=source_path or (api_key_info.source_path if api_key_info else None),
            target_url=None,  # 或者None，根据具体情况
            status_code=404,  # 或其他错误码
            response_time_ms=int((time.time() - start_time) * 1000),
            error_message="No matching route found"  # 或其他错误信息
        )
        
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No matching route found"
        )
    
    # 检查认证要求
    if route.auth_required and not api_key_info:
        # 记录401错误的审计日志
        audit_service = AuditService(db)
        await audit_service.create_enhanced_log(
            request=request,
            request_id=request_id,
            api_key=api_key_info.key_value if api_key_info else None,
            source_path=source_path or (api_key_info.source_path if api_key_info else None),
            target_url=None,  # 或者None，根据具体情况
            status_code=401,  # 或其他错误码
            response_time_ms=int((time.time() - start_time) * 1000),
            error_message="Authentication required for this route"  # 或其他错误信息
        )
        
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required for this route"
        )
    
    try:
        # 执行代理转发
        proxy_result = await route_manager.proxy_request(request, route, request_id)
        
        # 记录成功的审计日志
        audit_service = AuditService(db)
        await audit_service.create_enhanced_log(
            request=request,
            request_id=request_id,
            api_key=api_key_info.key_value,
            source_path=source_path or api_key_info.source_path,
            target_url=proxy_result["target_url"],
            status_code=proxy_result["status_code"],
            response_time_ms=proxy_result["response_time_ms"],
            response_content=proxy_result["content"],
            response_headers=proxy_result["headers"]
        )
        
        # 构建响应
        response = Response(
            content=proxy_result["content"],
            status_code=proxy_result["status_code"],
            media_type=proxy_result["headers"].get("content-type", "application/octet-stream")
        )
        
        # 复制响应头（排除某些系统头）
        excluded_headers = {
            "content-length", "content-encoding", "transfer-encoding", 
            "connection", "upgrade", "server"
        }
        for key, value in proxy_result["headers"].items():
            if key.lower() not in excluded_headers:
                response.headers[key] = value
        
        return response
        
    except HTTPException as e:
        # 记录失败的审计日志
        end_time = time.time()
        response_time_ms = int((end_time - start_time) * 1000)
        
        audit_service = AuditService(db)
        await audit_service.create_enhanced_log(
            request=request,
            request_id=request_id,
            api_key=api_key_info.key_value,
            source_path=source_path or api_key_info.source_path,
            target_url=proxy_result.get("target_url") if "proxy_result" in locals() else None,
            status_code=e.status_code,
            response_time_ms=response_time_ms,
            error_message=e.detail
        )
        
        raise e
    
    except Exception as e:
        # 记录未知错误的审计日志
        audit_service = AuditService(db)
        await audit_service.create_enhanced_log(
            request=request,
            request_id=request_id,
            api_key=api_key_info.key_value if api_key_info else None,
            source_path=source_path or (api_key_info.source_path if api_key_info else None),
            target_url=None,  # 或者None，根据具体情况
            status_code=500,  # 或其他错误码
            response_time_ms=int((time.time() - start_time) * 1000),
            error_message=str(e)  # 或其他错误信息
        )
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        ) 