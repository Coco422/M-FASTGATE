"""
认证中间件
"""

from fastapi import HTTPException, status, Request, Depends, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional
from sqlalchemy.orm import Session
from ..database import get_db
from ..services.key_manager import KeyManager
from ..models.api_key import APIKeyResponse
from ..config import settings


class APIKeyAuth:
    """API Key 认证类"""
    
    def __init__(self):
        self.security = HTTPBearer(auto_error=False)
    
    async def __call__(self, request: Request) -> Optional[APIKeyResponse]:
        """
        验证API Key
        
        Args:
            request: FastAPI请求对象
            
        Returns:
            APIKeyResponse: 验证成功返回API Key信息，失败返回None
            
        Raises:
            HTTPException: 认证失败时抛出401错误
        """
        # 从Header中获取API Key
        api_key = request.headers.get("X-API-Key")
        
        if not api_key:
            # 尝试从Authorization Header获取
            auth_header = request.headers.get("Authorization")
            if auth_header and auth_header.startswith("Bearer "):
                api_key = auth_header[7:]  # 移除 "Bearer " 前缀
        
        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="API Key is required",
                headers={"WWW-Authenticate": "Bearer"}
            )
        
        # 验证API Key
        db: Session = next(get_db())
        try:
            key_manager = KeyManager(db)
            api_key_info = key_manager.validate_key(api_key)
            
            if not api_key_info:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid or expired API Key",
                    headers={"WWW-Authenticate": "Bearer"}
                )
            
            # 更新使用统计
            key_manager.update_usage(api_key)
            
            return api_key_info
            
        finally:
            db.close()


class OptionalAPIKeyAuth:
    """可选的API Key认证类（用于某些不需要强制认证的接口）"""
    
    async def __call__(self, request: Request) -> Optional[APIKeyResponse]:
        """
        可选验证API Key
        
        Args:
            request: FastAPI请求对象
            
        Returns:
            APIKeyResponse: 验证成功返回API Key信息，失败返回None（不抛出异常）
        """
        try:
            auth = APIKeyAuth()
            return await auth(request)
        except HTTPException:
            return None


# 创建全局认证实例
api_key_auth = APIKeyAuth()
optional_api_key_auth = OptionalAPIKeyAuth()


def verify_admin_token(token: str = Query(..., description="管理员令牌")):
    """验证管理员令牌"""
    if token != settings.security['admin_token']:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin token"
        )
    return token


def get_api_key_from_request(request: Request) -> Optional[str]:
    """
    从请求中提取API Key
    支持两种方式：
    1. X-API-Key header
    2. Authorization Bearer token
    """
    # 方式1：X-API-Key header
    api_key = request.headers.get("X-API-Key")
    if api_key:
        return api_key
    
    # 方式2：Authorization Bearer
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        return auth_header[7:]  # 移除 "Bearer " 前缀
    
    return None


def get_source_path(request: Request) -> Optional[str]:
    """
    从请求中获取来源路径
    
    Args:
        request: FastAPI请求对象
        
    Returns:
        str: 来源路径
    """
    return request.headers.get("X-Source-Path")


def get_client_ip(request: Request) -> str:
    """
    获取客户端IP地址
    
    Args:
        request: FastAPI请求对象
        
    Returns:
        str: 客户端IP地址
    """
    # 优先从代理头获取真实IP
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip
    
    # 回退到直接连接IP
    if hasattr(request, "client") and request.client:
        return request.client.host
    
    return "unknown"


def get_user_agent(request: Request) -> Optional[str]:
    """
    获取用户代理字符串
    
    Args:
        request: FastAPI请求对象
        
    Returns:
        str: User-Agent字符串
    """
    return request.headers.get("User-Agent")


async def api_key_auth(
    request: Request,
    db: Session = Depends(get_db)
) -> APIKeyResponse:
    """
    API Key 认证依赖
    
    Returns:
        APIKeyResponse: 验证通过的API Key信息
        
    Raises:
        HTTPException: 认证失败
    """
    api_key = get_api_key_from_request(request)
    
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API Key is required. Use X-API-Key header or Authorization Bearer token."
        )
    
    # 验证API Key
    key_manager = KeyManager(db)
    api_key_info = key_manager.validate_key(api_key)
    
    if not api_key_info:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired API Key"
        )
    
    # 更新使用统计
    key_manager.update_usage(api_key)

    return api_key_info


# 可选认证（允许未认证的请求通过）
async def optional_api_key_auth(
    request: Request,
    db: Session = Depends(get_db)
) -> Optional[APIKeyResponse]:
    """
    可选的API Key认证
    如果提供了API Key则验证，否则返回None
    """
    try:
        return await api_key_auth(request, db)
    except HTTPException:
        return None 