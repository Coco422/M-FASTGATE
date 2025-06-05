"""
管理接口
"""

from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from ..database import get_db
from ..middleware.auth import verify_admin_token
from ..services.key_manager import KeyManager
from ..services.audit_service import AuditService
from ..services.dynamic_route_manager import DynamicRouteManager
from ..models.api_key import APIKeyCreate, APIKeyUpdate, APIKeyResponse
from ..models.route_config import RouteConfigCreate, RouteConfigUpdate, RouteConfigResponse
from ..models.audit_log import AuditLogResponse
from ..config import settings

router = APIRouter()


# ============= API Key 管理 =============

@router.post("/keys")
async def create_api_key(
    key_data: APIKeyCreate,
    db: Session = Depends(get_db),
    token: str = Depends(verify_admin_token)
) -> APIKeyResponse:
    """
    创建新的 API Key
    """
    key_manager = KeyManager(db)
    return key_manager.create_key(key_data)


@router.get("/keys")
async def list_api_keys(
    skip: int = Query(0, ge=0, description="跳过的记录数"),
    limit: int = Query(100, ge=1, le=1000, description="返回的记录数"),
    source_path: Optional[str] = Query(None, description="按来源路径过滤"),
    is_active: Optional[bool] = Query(None, description="按活跃状态过滤"),
    db: Session = Depends(get_db),
    token: str = Depends(verify_admin_token)
) -> List[APIKeyResponse]:
    """
    获取 API Key 列表
    """
    key_manager = KeyManager(db)
    return key_manager.list_keys(skip=skip, limit=limit, source_path=source_path, is_active=is_active)


@router.get("/keys/{key_id}")
async def get_api_key(
    key_id: str,
    db: Session = Depends(get_db),
    token: str = Depends(verify_admin_token)
) -> APIKeyResponse:
    """
    获取 API Key 详情
    """
    key_manager = KeyManager(db)
    api_key = key_manager.get_key(key_id)
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API Key not found"
        )
    return api_key


@router.put("/keys/{key_id}")
async def update_api_key(
    key_id: str,
    key_data: APIKeyUpdate,
    db: Session = Depends(get_db),
    token: str = Depends(verify_admin_token)
) -> APIKeyResponse:
    """
    更新 API Key
    """
    key_manager = KeyManager(db)
    api_key = key_manager.update_key(key_id, key_data)
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API Key not found"
        )
    return api_key


@router.delete("/keys/{key_id}")
async def delete_api_key(
    key_id: str,
    db: Session = Depends(get_db),
    token: str = Depends(verify_admin_token)
):
    """
    删除 API Key
    """
    key_manager = KeyManager(db)
    success = key_manager.delete_key(key_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API Key not found"
        )
    return {"message": "API Key deleted successfully"}


# ============= 动态路由管理 =============

@router.post("/routes")
async def create_route(
    route_data: RouteConfigCreate,
    db: Session = Depends(get_db),
    token: str = Depends(verify_admin_token)
) -> RouteConfigResponse:
    """
    创建新的路由配置
    """
    route_manager = DynamicRouteManager(db)
    return route_manager.create_route(route_data)


@router.get("/routes")
async def list_routes(
    db: Session = Depends(get_db),
    token: str = Depends(verify_admin_token)
) -> List[RouteConfigResponse]:
    """
    获取所有路由配置
    """
    route_manager = DynamicRouteManager(db)
    return route_manager.get_routes()


@router.get("/routes/{route_id}")
async def get_route(
    route_id: str,
    db: Session = Depends(get_db),
    token: str = Depends(verify_admin_token)
) -> RouteConfigResponse:
    """
    获取单个路由配置详情
    """
    route_manager = DynamicRouteManager(db)
    route = route_manager.get_route(route_id)
    if not route:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Route not found"
        )
    return route


@router.put("/routes/{route_id}")
async def update_route(
    route_id: str,
    route_data: RouteConfigUpdate,
    db: Session = Depends(get_db),
    token: str = Depends(verify_admin_token)
) -> RouteConfigResponse:
    """
    更新路由配置
    """
    route_manager = DynamicRouteManager(db)
    route = route_manager.update_route(route_id, route_data)
    if not route:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Route not found"
        )
    return route


@router.delete("/routes/{route_id}")
async def delete_route(
    route_id: str,
    db: Session = Depends(get_db),
    token: str = Depends(verify_admin_token)
):
    """
    删除路由配置
    """
    route_manager = DynamicRouteManager(db)
    success = route_manager.delete_route(route_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Route not found"
        )
    return {"message": "Route deleted successfully"}


# ============= 审计日志 =============

@router.get("/logs")
async def get_audit_logs(
    skip: int = Query(0, ge=0, description="跳过的记录数"),
    limit: int = Query(50, ge=1, le=1000, description="返回的记录数"),
    api_key: Optional[str] = Query(None, description="按 API Key 过滤"),
    source_path: Optional[str] = Query(None, description="按来源路径过滤"),
    method: Optional[str] = Query(None, description="按请求方法过滤"),
    status_code: Optional[int] = Query(None, description="按状态码过滤"),
    db: Session = Depends(get_db),
    token: str = Depends(verify_admin_token)
):
    """
    获取审计日志
    """
    audit_service = AuditService(db)
    return audit_service.get_logs(
        offset=skip, 
        limit=limit,
        api_key=api_key,
        source_path=source_path,
        method=method,
        status_code=status_code
    )


@router.get("/metrics")
async def get_metrics(
    db: Session = Depends(get_db),
    token: str = Depends(verify_admin_token)
):
    """
    获取统计指标
    """
    audit_service = AuditService(db)
    return audit_service.get_stats()

@router.get("/metrics/hourly")
async def get_hourly_metrics(
    hours: int = Query(24, ge=1, le=168, description="获取最近多少小时的数据"),
    db: Session = Depends(get_db),
    token: str = Depends(verify_admin_token)
):
    """
    获取按小时统计的指标数据
    """
    audit_service = AuditService(db)
    return audit_service.get_hourly_metrics(hours)


@router.get("/metrics/trends")
async def get_trends_metrics(
    days: int = Query(30, ge=1, le=365, description="获取最近多少天的数据"),
    group_by: str = Query("day", regex="^(day|hour)$", description="分组方式"),
    db: Session = Depends(get_db),
    token: str = Depends(verify_admin_token)
):
    """
    获取趋势数据
    """
    audit_service = AuditService(db)
    return audit_service.get_trends_data(days, group_by)

# ============= 原有的路由配置兼容 =============

@router.get("/routes-legacy")
async def get_routes_legacy(
    token: str = Depends(verify_admin_token)
):
    """
    获取路由配置（兼容原有接口）
    """
    from ..config import routes_config
    return {
        "routes": [
            {
                "name": route.name,
                "path_prefix": route.path_prefix,
                "targets": [{"url": target.url, "timeout": target.timeout} for target in route.targets],
                "auth_required": route.auth_required,
                "rate_limit": route.rate_limit
            }
            for route in routes_config
        ]
    } 