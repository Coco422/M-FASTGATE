"""
模型端点配置数据模型
"""

from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy import Column, String, DateTime, Boolean, Integer, Text, JSON
from sqlalchemy.sql import func
from pydantic import BaseModel
from ..database import Base
import uuid


class CloudProxyConfig(BaseModel):
    """云天代理服务配置"""
    host: str = "10.101.32.14"
    port: int = 34094
    base_path: str = "/openapi/proxy"


class ModelRouteDB(Base):
    """模型路由配置数据库模型"""
    __tablename__ = "model_routes"
    
    id = Column(String(50), primary_key=True, index=True)
    model_name = Column(String(100), unique=True, index=True, nullable=False)
    endpoint_type = Column(String(20), nullable=False)  # 'chat' 或 'embedding'
    proxy_path = Column(String(500), nullable=False)    # '/**' 或 '/embed'
    parameters = Column(Text, nullable=True)            # 模型参数配置 (JSON字符串)
    health_check_path = Column(String(500), default="/health")
    timeout = Column(Integer, default=30)
    max_retries = Column(Integer, default=3)
    is_active = Column(Boolean, default=True, index=True)
    health_status = Column(String(20), default="unknown")
    last_health_check = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=func.now(), index=True)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class ModelUsageStatsDB(Base):
    """模型使用统计数据库模型"""
    __tablename__ = "model_usage_stats"
    
    id = Column(String(50), primary_key=True, index=True)
    model_name = Column(String(100), nullable=False, index=True)
    api_key = Column(String(100), nullable=True, index=True)
    source_path = Column(String(100), nullable=True)
    request_count = Column(Integer, default=1)
    total_tokens = Column(Integer, default=0)
    total_response_time_ms = Column(Integer, default=0)
    error_count = Column(Integer, default=0)
    success_count = Column(Integer, default=0)
    date = Column(String(10), nullable=False, index=True)  # YYYY-MM-DD
    hour = Column(Integer, nullable=False, index=True)     # 0-23
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class ModelEndpointConfig(BaseModel):
    """模型端点配置"""
    model_name: str
    endpoint_type: str  # "chat" 或 "embedding"
    proxy_path: str     # "/**" 或 "/embed"
    parameters: Optional[Dict[str, Any]] = None
    health_check_path: str = "/health"
    timeout: int = 30
    max_retries: int = 3
    is_active: bool = True


class ModelRouteCreate(BaseModel):
    """创建模型路由配置请求"""
    model_name: str
    endpoint_type: str  # "chat" 或 "embedding"
    proxy_path: str     # "/**" 或 "/embed"
    parameters: Optional[Dict[str, Any]] = None
    timeout: Optional[int] = 30
    max_retries: Optional[int] = 3


class ModelRouteUpdate(BaseModel):
    """更新模型路由配置请求"""
    model_name: Optional[str] = None
    endpoint_type: Optional[str] = None
    proxy_path: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None
    timeout: Optional[int] = None
    max_retries: Optional[int] = None
    is_active: Optional[bool] = None


class ModelRouteResponse(BaseModel):
    """模型路由配置响应"""
    id: str
    model_name: str
    endpoint_type: str
    proxy_path: str
    parameters: Optional[Dict[str, Any]]
    health_check_path: str
    timeout: int
    max_retries: int
    is_active: bool
    health_status: str
    last_health_check: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class RouteResult(BaseModel):
    """路由结果"""
    target_url: str
    enhanced_body: Dict[str, Any]
    enhanced_headers: Dict[str, str]
    endpoint_config: ModelEndpointConfig


def generate_model_route_id() -> str:
    """生成模型路由ID"""
    return f"route_{uuid.uuid4().hex[:12]}"


def generate_usage_stats_id() -> str:
    """生成使用统计ID"""
    return f"stats_{uuid.uuid4().hex[:12]}" 