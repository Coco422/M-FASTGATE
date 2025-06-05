"""
模型路由管理API接口
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..middleware.auth import verify_admin_token
from ..models.model_endpoint import (
    ModelRouteCreate, ModelRouteUpdate, ModelRouteResponse
)
from ..services.model_route_manager import ModelRouteManager
from ..services.intelligent_router import IntelligentRouter

router = APIRouter(prefix="/model-routes", tags=["Model Routes"])


@router.get("", response_model=List[ModelRouteResponse])
async def list_model_routes(
    db: Session = Depends(get_db),
    token: str = Depends(verify_admin_token)
):
    """获取所有模型路由配置"""
    route_manager = ModelRouteManager(db)
    return route_manager.list_routes()


@router.get("/{model_name}", response_model=ModelRouteResponse)
async def get_model_route(
    model_name: str,
    db: Session = Depends(get_db),
    token: str = Depends(verify_admin_token)
):
    """获取指定模型的路由配置"""
    route_manager = ModelRouteManager(db)
    route = route_manager.get_route_by_model(model_name)
    if not route:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model route for '{model_name}' not found"
        )
    return route


@router.post("", response_model=ModelRouteResponse)
async def create_model_route(
    route_data: ModelRouteCreate,
    db: Session = Depends(get_db),
    token: str = Depends(verify_admin_token)
):
    """创建模型路由配置"""
    route_manager = ModelRouteManager(db)
    return route_manager.add_route(route_data)


@router.put("/{model_name}", response_model=ModelRouteResponse)
async def update_model_route(
    model_name: str,
    route_data: ModelRouteUpdate,
    db: Session = Depends(get_db),
    token: str = Depends(verify_admin_token)
):
    """更新模型路由配置"""
    route_manager = ModelRouteManager(db)
    result = route_manager.update_route(model_name, route_data)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model route for '{model_name}' not found"
        )
    return result


@router.delete("/{model_name}")
async def delete_model_route(
    model_name: str,
    db: Session = Depends(get_db),
    token: str = Depends(verify_admin_token)
):
    """删除模型路由配置"""
    route_manager = ModelRouteManager(db)
    success = route_manager.delete_route(model_name)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model route for '{model_name}' not found"
        )
    return {"message": f"Model route for '{model_name}' deleted successfully"}


@router.post("/{model_name}/toggle")
async def toggle_model_route(
    model_name: str,
    is_active: bool,
    db: Session = Depends(get_db),
    token: str = Depends(verify_admin_token)
):
    """切换模型路由状态"""
    route_manager = ModelRouteManager(db)
    result = route_manager.toggle_route_status(model_name, is_active)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model route for '{model_name}' not found"
        )
    return {
        "message": f"Model route for '{model_name}' {'activated' if is_active else 'deactivated'}",
        "route": result
    }


@router.get("/info/available")
async def get_available_models(
    db: Session = Depends(get_db)
):
    """获取可用模型信息（公开接口）"""
    router_service = IntelligentRouter(db)
    return router_service.get_available_models()


@router.get("/info/{model_name}")
async def get_model_info(
    model_name: str,
    db: Session = Depends(get_db)
):
    """获取指定模型的详细信息（公开接口）"""
    router_service = IntelligentRouter(db)
    info = router_service.get_model_info(model_name)
    if not info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model '{model_name}' not found"
        )
    return info


@router.post("/validate/{model_name}")
async def validate_model_request(
    model_name: str,
    request_body: dict,
    db: Session = Depends(get_db)
):
    """验证模型请求格式（公开接口）"""
    router_service = IntelligentRouter(db)
    return router_service.validate_model_request(model_name, request_body)


@router.get("/health/{model_name}")
async def health_check_model(
    model_name: str,
    db: Session = Depends(get_db),
    token: str = Depends(verify_admin_token)
):
    """检查指定模型的健康状态"""
    router_service = IntelligentRouter(db)
    return await router_service.health_check_model(model_name)


@router.get("/health/all")
async def health_check_all_models(
    db: Session = Depends(get_db),
    token: str = Depends(verify_admin_token)
):
    """检查所有模型的健康状态"""
    route_manager = ModelRouteManager(db)
    router_service = IntelligentRouter(db)
    
    models = route_manager.get_available_models()
    results = []
    
    for model_name in models:
        health_result = await router_service.health_check_model(model_name)
        results.append(health_result)
    
    return {
        "total_models": len(models),
        "results": results,
        "summary": {
            "healthy": len([r for r in results if r.get("status") == "healthy"]),
            "unhealthy": len([r for r in results if r.get("status") == "unhealthy"]),
            "error": len([r for r in results if r.get("status") == "error"]),
            "not_found": len([r for r in results if r.get("status") == "not_found"])
        }
    } 