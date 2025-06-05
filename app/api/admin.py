"""
M-FastGate v0.2.0 管理接口
"""

from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from ..database import get_db
from ..middleware.auth import verify_admin_token
from ..services.key_manager import KeyManager
from ..services.audit_service import AuditService
from ..models.api_key import APIKeyCreate, APIKeyUpdate, APIKeyResponse
from ..models.proxy_route import ProxyRouteCreate, ProxyRouteUpdate, ProxyRouteResponse
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


# ============= 代理路由管理 =============

@router.post("/routes")
async def create_proxy_route(
    route_data: ProxyRouteCreate,
    db: Session = Depends(get_db),
    token: str = Depends(verify_admin_token)
) -> ProxyRouteResponse:
    """
    创建新的代理路由配置
    """
    from ..models.proxy_route import ProxyRoute
    
    # 创建代理路由
    db_route = ProxyRoute(**route_data.dict())
    db.add(db_route)
    db.commit()
    db.refresh(db_route)
    
    return ProxyRouteResponse.from_orm(db_route)


@router.get("/routes")
async def list_proxy_routes(
    skip: int = Query(0, ge=0, description="跳过的记录数"),
    limit: int = Query(100, ge=1, le=1000, description="返回的记录数"),
    is_active: Optional[bool] = Query(None, description="按活跃状态过滤"),
    db: Session = Depends(get_db),
    token: str = Depends(verify_admin_token)
) -> List[ProxyRouteResponse]:
    """
    获取代理路由配置列表
    """
    from ..models.proxy_route import ProxyRoute
    
    query = db.query(ProxyRoute)
    
    if is_active is not None:
        query = query.filter(ProxyRoute.is_active == is_active)
    
    routes = query.offset(skip).limit(limit).all()
    return [ProxyRouteResponse.from_orm(route) for route in routes]


@router.get("/routes/{route_id}")
async def get_proxy_route(
    route_id: str,
    db: Session = Depends(get_db),
    token: str = Depends(verify_admin_token)
) -> ProxyRouteResponse:
    """
    获取单个代理路由配置详情
    """
    from ..models.proxy_route import ProxyRoute
    
    route = db.query(ProxyRoute).filter(ProxyRoute.id == route_id).first()
    if not route:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Proxy route not found"
        )
    return ProxyRouteResponse.from_orm(route)


@router.put("/routes/{route_id}")
async def update_proxy_route(
    route_id: str,
    route_data: ProxyRouteUpdate,
    db: Session = Depends(get_db),
    token: str = Depends(verify_admin_token)
) -> ProxyRouteResponse:
    """
    更新代理路由配置
    """
    from ..models.proxy_route import ProxyRoute
    
    route = db.query(ProxyRoute).filter(ProxyRoute.id == route_id).first()
    if not route:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Proxy route not found"
        )
    
    # 更新字段
    update_data = route_data.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(route, field, value)
    
    route.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(route)
    
    return ProxyRouteResponse.from_orm(route)


@router.delete("/routes/{route_id}")
async def delete_proxy_route(
    route_id: str,
    db: Session = Depends(get_db),
    token: str = Depends(verify_admin_token)
):
    """
    删除代理路由配置
    """
    from ..models.proxy_route import ProxyRoute
    
    route = db.query(ProxyRoute).filter(ProxyRoute.id == route_id).first()
    if not route:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Proxy route not found"
        )
    
    db.delete(route)
    db.commit()
    
    return {"message": "Proxy route deleted successfully"}


# ============= 审计日志 =============

@router.get("/logs")
async def get_audit_logs(
    skip: int = Query(0, ge=0, description="跳过的记录数"),
    limit: int = Query(50, ge=1, le=10000, description="返回的记录数"),
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

 