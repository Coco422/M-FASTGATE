"""
API网关路由接口 - 专门处理统一的聊天完成端点
"""

from fastapi import APIRouter, Request, Depends, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ..database import get_db
from ..middleware.auth import api_key_auth, get_client_ip, get_user_agent, get_source_path
from ..services.api_gateway_service import api_gateway_service
from ..services.audit_service import AuditService
from ..models.api_key import APIKeyResponse

router = APIRouter()


@router.post("/proxy/miniai/v2/chat/completions")
async def chat_completions_gateway(
    request: Request,
    db: Session = Depends(get_db),
    api_key_info: APIKeyResponse = Depends(api_key_auth)
):
    """
    统一的聊天完成API网关端点
    
    所有用户(key1, key2, key3...)都请求这个端点
    系统会：
    1. 验证用户API Key
    2. 异步记录详细审计日志
    3. 清洗请求参数
    4. 使用固定的real-key转发到后端
    5. 返回响应（支持流式）
    """
    # 获取请求元信息
    client_ip = get_client_ip(request)
    user_agent = get_user_agent(request)
    source_path = get_source_path(request)
    
    # 创建审计服务
    audit_service = AuditService(db)
    
    # 处理请求
    result = await api_gateway_service.process_chat_completions(
        request=request,
        api_key_info=api_key_info,
        audit_service=audit_service,
        client_ip=client_ip,
        user_agent=user_agent,
        source_path=source_path
    )
    
    # 如果是流式响应，直接返回StreamingResponse
    if isinstance(result, StreamingResponse):
        return result
    
    # 普通响应处理
    response = Response(
        content=result["content"],
        status_code=result["status_code"],
        media_type=result["headers"].get("content-type", "application/json")
    )
    
    # 复制响应头
    excluded_headers = {
        "content-length", "content-encoding", "transfer-encoding", 
        "connection", "upgrade", "server"
    }
    for key, value in result["headers"].items():
        if key.lower() not in excluded_headers:
            response.headers[key] = value
    
    return response


@router.get("/proxy/miniai/v2/chat/completions")
async def chat_completions_info():
    """
    获取聊天完成端点信息
    """
    return {
        "endpoint": "/proxy/miniai/v2/chat/completions",
        "method": "POST",
        "description": "Unified chat completions gateway endpoint",
        "supported_features": [
            "API Key authentication",
            "Async audit logging", 
            "Parameter cleaning",
            "Streaming responses",
            "Error handling"
        ],
        "backend": {
            "url": "http://172.16.99.32:1030/miniai/v2/chat/completions",
            "authentication": "Fixed real-key"
        }
    }


@router.options("/proxy/miniai/v2/chat/completions")
async def chat_completions_options():
    """
    处理CORS预检请求
    """
    return Response(
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST, GET, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization, X-API-Key",
            "Access-Control-Max-Age": "86400"
        }
    ) 