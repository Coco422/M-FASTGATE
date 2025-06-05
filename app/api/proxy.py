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
from ..services.intelligent_router import IntelligentRouter
from ..models.api_key import APIKeyResponse
from ..models.audit_log import AuditLogCreate, generate_request_id
from ..config import settings

router = APIRouter()


@router.api_route("/smart/{path:path}", methods=["POST"])
async def smart_proxy_request(
    path: str,
    request: Request,
    db: Session = Depends(get_db),
    api_key_info: APIKeyResponse = Depends(api_key_auth)
):
    """
    智能代理转发接口 - Phase 2.4 核心功能
    根据请求体中的model字段智能路由到对应的模型服务
    
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
    request_path = f"/smart/{path}"
    
    # 检查模型路由功能是否启用
    if not getattr(settings.model_routing, 'enabled', True):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Model routing service is disabled"
        )
    
    # 初始化变量
    request_body = None
    route_result = None
    model_name = None
    
    try:
        # 获取请求体
        request_body = await request.json()
        model_name = request_body.get("model")
        
        # 创建智能路由器
        intelligent_router = IntelligentRouter(db)
        
        # 执行智能路由
        route_result = await intelligent_router.route_request(
            request=request,
            request_body=request_body,
            api_key=api_key_info.key_value,
            source_path=source_path or api_key_info.source_path
        )
        
        # 使用httpx转发请求到云天代理
        import httpx
        response = None
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(
                    timeout=route_result.endpoint_config.timeout,
                    read=route_result.endpoint_config.timeout * 2
                )
            ) as client:
                
                # 转发请求
                response = await client.post(
                    route_result.target_url,
                    json=route_result.enhanced_body,
                    headers=route_result.enhanced_headers
                )
        except httpx.TimeoutException as timeout_exc:
            # 处理超时异常
            end_time = time.time()
            response_time_ms = int((end_time - start_time) * 1000)
            
            audit_service = AuditService(db)
            await audit_service.create_enhanced_log(
                request=request,
                request_id=request_id,
                api_key=api_key_info.key_value,
                source_path=source_path or api_key_info.source_path,
                target_url=route_result.target_url,
                status_code=504,  # Gateway Timeout
                response_time_ms=response_time_ms,
                error_message=f"Request timeout: {str(timeout_exc)}",
                model_name=route_result.endpoint_config.model_name,
                routing_time_ms=0
            )
            
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail=f"Request to model service timed out after {route_result.endpoint_config.timeout}s"
            )
        except httpx.ConnectError as connect_exc:
            # 处理连接异常
            end_time = time.time()
            response_time_ms = int((end_time - start_time) * 1000)
            
            audit_service = AuditService(db)
            await audit_service.create_enhanced_log(
                request=request,
                request_id=request_id,
                api_key=api_key_info.key_value,
                source_path=source_path or api_key_info.source_path,
                target_url=route_result.target_url,
                status_code=502,  # Bad Gateway
                response_time_ms=response_time_ms,
                error_message=f"Connection failed: {str(connect_exc)}",
                model_name=route_result.endpoint_config.model_name,
                routing_time_ms=0
            )
            
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Failed to connect to model service"
            )
        except httpx.HTTPError as http_error:
            # 处理其他HTTP错误
            end_time = time.time()
            response_time_ms = int((end_time - start_time) * 1000)
            
            audit_service = AuditService(db)
            await audit_service.create_enhanced_log(
                request=request,
                request_id=request_id,
                api_key=api_key_info.key_value,
                source_path=source_path or api_key_info.source_path,
                target_url=route_result.target_url,
                status_code=503,  # Service Unavailable
                response_time_ms=response_time_ms,
                error_message=f"HTTP error: {str(http_error)}",
                model_name=route_result.endpoint_config.model_name,
                routing_time_ms=0
            )
            
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Model service error"
            )
            
            end_time = time.time()
            response_time_ms = int((end_time - start_time) * 1000)
            
            # 处理流式响应
            if response.headers.get("content-type", "").startswith("text/event-stream"):
                async def stream_wrapper():
                    async for chunk in response.aiter_bytes():
                        yield chunk
                
                # 记录流式响应的审计日志
                audit_service = AuditService(db)
                await audit_service.create_enhanced_log(
                    request=request,
                    request_id=request_id,
                    api_key=api_key_info.key_value,
                    source_path=source_path or api_key_info.source_path,
                    target_url=route_result.target_url,
                    status_code=response.status_code,
                    response_time_ms=response_time_ms,
                    request_body=route_result.enhanced_body,
                    response_headers=dict(response.headers),
                    is_stream=True,
                    model_name=route_result.endpoint_config.model_name,
                    routing_time_ms=getattr(route_result, 'routing_time_ms', 0)
                )
                
                return StreamingResponse(
                    stream_wrapper(),
                    status_code=response.status_code,
                    headers=dict(response.headers),
                    media_type="text/event-stream"
                )
            
            # 非流式响应
            response_content = await response.aread()
            
            # 记录审计日志
            audit_service = AuditService(db)
            await audit_service.create_enhanced_log(
                request=request,
                request_id=request_id,
                api_key=api_key_info.key_value,
                source_path=source_path or api_key_info.source_path,
                target_url=route_result.target_url,
                status_code=response.status_code,
                response_time_ms=response_time_ms,
                request_body=route_result.enhanced_body,
                response_content=response_content,
                response_headers=dict(response.headers),
                model_name=route_result.endpoint_config.model_name,
                routing_time_ms=getattr(route_result, 'routing_time_ms', 0)
            )
            
            # 构建响应
            final_response = Response(
                content=response_content,
                status_code=response.status_code,
                media_type=response.headers.get("content-type", "application/json")
            )
            
            # 复制响应头
            excluded_headers = {
                "content-length", "content-encoding", "transfer-encoding", 
                "connection", "upgrade", "server"
            }
            for key, value in response.headers.items():
                if key.lower() not in excluded_headers:
                    final_response.headers[key] = value
            
            return final_response
            
    except HTTPException as http_exc:
        # 记录HTTP错误的审计日志
        end_time = time.time()
        response_time_ms = int((end_time - start_time) * 1000)
        
        audit_service = AuditService(db)
        await audit_service.create_enhanced_log(
            request=request,
            request_id=request_id,
            api_key=api_key_info.key_value,
            source_path=source_path or api_key_info.source_path,
            target_url=getattr(route_result, 'target_url', None) if route_result else None,
            status_code=http_exc.status_code,
            response_time_ms=response_time_ms,
            error_message=http_exc.detail,
            model_name=model_name,
            routing_time_ms=0
        )
        
        raise http_exc
    except Exception as e:
        # 记录其他错误的审计日志
        end_time = time.time()
        response_time_ms = int((end_time - start_time) * 1000)
        
        audit_service = AuditService(db)
        await audit_service.create_enhanced_log(
            request=request,
            request_id=request_id,
            api_key=api_key_info.key_value,
            source_path=source_path or api_key_info.source_path,
            target_url=getattr(route_result, 'target_url', None) if route_result else None,
            status_code=500,
            response_time_ms=response_time_ms,
            error_message=str(e),
            model_name=model_name,
            routing_time_ms=0
        )
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Smart routing failed: {str(e)}"
        )


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