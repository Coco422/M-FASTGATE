"""
模型路由管理服务
"""

import json
import time
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from ..models.model_endpoint import (
    ModelRouteDB, ModelRouteCreate, ModelRouteUpdate, 
    ModelRouteResponse, ModelEndpointConfig, generate_model_route_id
)
from ..config import settings


class ModelRouteManager:
    """模型路由管理器"""
    
    def __init__(self, db: Session):
        self.db = db
        self._config_cache = {}
        self._load_config()
    
    def _load_config(self):
        """从数据库加载路由配置到缓存"""
        routes = self.db.query(ModelRouteDB).filter(ModelRouteDB.is_active == True).all()
        for route in routes:
            config = self._db_to_config(route)
            self._config_cache[route.model_name] = config
    
    def _db_to_config(self, db_route: ModelRouteDB) -> ModelEndpointConfig:
        """转换数据库模型到配置对象"""
        parameters = None
        if db_route.parameters:
            try:
                parameters = json.loads(db_route.parameters) if isinstance(db_route.parameters, str) else db_route.parameters
            except (json.JSONDecodeError, TypeError):
                parameters = {}
        
        return ModelEndpointConfig(
            model_name=db_route.model_name,
            endpoint_type=db_route.endpoint_type,
            proxy_path=db_route.proxy_path,
            parameters=parameters,
            health_check_path=db_route.health_check_path or "/health",
            timeout=db_route.timeout or 30,
            max_retries=db_route.max_retries or 3,
            is_active=db_route.is_active
        )
    
    def _to_response(self, db_route: ModelRouteDB) -> ModelRouteResponse:
        """转换数据库模型到响应模型"""
        from datetime import datetime
        
        parameters = None
        if db_route.parameters:
            try:
                parameters = json.loads(db_route.parameters) if isinstance(db_route.parameters, str) else db_route.parameters
            except (json.JSONDecodeError, TypeError):
                parameters = {}
        
        # 处理可能为NULL的datetime字段
        now = datetime.now()
        created_at = db_route.created_at or now
        updated_at = db_route.updated_at or now
        
        return ModelRouteResponse(
            id=db_route.id,
            model_name=db_route.model_name,
            endpoint_type=db_route.endpoint_type,
            proxy_path=db_route.proxy_path,
            parameters=parameters,
            health_check_path=db_route.health_check_path or "/health",
            timeout=db_route.timeout or 30,
            max_retries=db_route.max_retries or 3,
            is_active=db_route.is_active,
            health_status=db_route.health_status or "unknown",
            last_health_check=db_route.last_health_check,
            created_at=created_at,
            updated_at=updated_at
        )
    
    def get_endpoint(self, model_name: str) -> Optional[ModelEndpointConfig]:
        """获取模型端点配置"""
        # 优先从缓存获取
        if model_name in self._config_cache:
            return self._config_cache[model_name]
        
        # 从数据库查询
        route = self.db.query(ModelRouteDB).filter(
            ModelRouteDB.model_name == model_name,
            ModelRouteDB.is_active == True
        ).first()
        
        if route:
            config = self._db_to_config(route)
            self._config_cache[model_name] = config
            return config
        
        return None
    
    def list_routes(self) -> List[ModelRouteResponse]:
        """获取所有模型路由配置"""
        routes = self.db.query(ModelRouteDB).order_by(ModelRouteDB.created_at.desc()).all()
        return [self._to_response(route) for route in routes]
    
    def get_route(self, route_id: str) -> Optional[ModelRouteResponse]:
        """获取单个路由配置"""
        db_route = self.db.query(ModelRouteDB).filter(ModelRouteDB.id == route_id).first()
        return self._to_response(db_route) if db_route else None
    
    def get_route_by_model(self, model_name: str) -> Optional[ModelRouteResponse]:
        """根据模型名称获取路由配置"""
        db_route = self.db.query(ModelRouteDB).filter(ModelRouteDB.model_name == model_name).first()
        return self._to_response(db_route) if db_route else None
    
    def add_route(self, route_data: ModelRouteCreate) -> ModelRouteResponse:
        """添加模型路由"""
        # 检查模型名称是否已存在
        existing = self.db.query(ModelRouteDB).filter(ModelRouteDB.model_name == route_data.model_name).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Model route for '{route_data.model_name}' already exists"
            )
        
        # 验证端点类型
        if route_data.endpoint_type not in ["chat", "embedding"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="endpoint_type must be 'chat' or 'embedding'"
            )
        
        # 验证代理路径
        if route_data.endpoint_type == "embedding" and route_data.proxy_path != "/embed":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="embedding models must use '/embed' proxy path"
            )
        elif route_data.endpoint_type == "chat" and route_data.proxy_path != "/**":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="chat models must use '/**' proxy path"
            )
        
        route_id = generate_model_route_id()
        
        # 序列化参数
        parameters_str = None
        if route_data.parameters:
            parameters_str = json.dumps(route_data.parameters)
        
        route_db = ModelRouteDB(
            id=route_id,
            model_name=route_data.model_name,
            endpoint_type=route_data.endpoint_type,
            proxy_path=route_data.proxy_path,
            parameters=parameters_str,
            timeout=route_data.timeout or 30,
            max_retries=route_data.max_retries or 3,
            is_active=True
        )
        
        self.db.add(route_db)
        self.db.commit()
        self.db.refresh(route_db)
        
        # 更新缓存
        self._refresh_cache()
        
        return self._to_response(route_db)
    
    def update_route(self, model_name: str, route_data: ModelRouteUpdate) -> Optional[ModelRouteResponse]:
        """更新模型路由"""
        route = self.db.query(ModelRouteDB).filter(
            ModelRouteDB.model_name == model_name
        ).first()
        
        if not route:
            return None
        
        # 更新字段
        update_data = route_data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            if key == "parameters" and value is not None:
                # 序列化参数
                setattr(route, key, json.dumps(value))
            elif hasattr(route, key):
                setattr(route, key, value)
        
        self.db.commit()
        self.db.refresh(route)
        
        # 更新缓存
        self._refresh_cache()
        
        return self._to_response(route)
    
    def delete_route(self, model_name: str) -> bool:
        """删除模型路由"""
        route = self.db.query(ModelRouteDB).filter(
            ModelRouteDB.model_name == model_name
        ).first()
        
        if not route:
            return False
        
        self.db.delete(route)
        self.db.commit()
        
        # 从缓存中移除
        self._config_cache.pop(model_name, None)
        
        return True
    
    def toggle_route_status(self, model_name: str, is_active: bool) -> Optional[ModelRouteResponse]:
        """切换路由状态"""
        route = self.db.query(ModelRouteDB).filter(
            ModelRouteDB.model_name == model_name
        ).first()
        
        if not route:
            return None
        
        route.is_active = is_active
        self.db.commit()
        self.db.refresh(route)
        
        # 更新缓存
        self._refresh_cache()
        
        return self._to_response(route)
    
    def _refresh_cache(self):
        """刷新缓存"""
        self._config_cache.clear()
        self._load_config()
    
    def get_available_models(self) -> List[str]:
        """获取可用的模型列表"""
        routes = self.db.query(ModelRouteDB).filter(ModelRouteDB.is_active == True).all()
        return [route.model_name for route in routes]
    
    def get_models_by_type(self, endpoint_type: str) -> List[str]:
        """根据端点类型获取模型列表"""
        routes = self.db.query(ModelRouteDB).filter(
            ModelRouteDB.is_active == True,
            ModelRouteDB.endpoint_type == endpoint_type
        ).all()
        return [route.model_name for route in routes] 