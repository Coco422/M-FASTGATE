"""
动态路由配置数据模型
"""

import uuid
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field
from sqlalchemy import Column, String, Text, DateTime, Boolean, Integer
from sqlalchemy.sql import func
from ..database import Base


# SQLAlchemy 数据库模型
class RouteConfigDB(Base):
    """路由配置数据库模型"""
    __tablename__ = "route_configs"

    route_id = Column(String(50), primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    target_url = Column(String(500), nullable=False)
    path_prefix = Column(String(200))  # 可选的路径前缀匹配
    is_active = Column(Boolean, default=True, index=True)
    timeout = Column(Integer, default=30)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


# Pydantic 请求/响应模型
class RouteConfigCreate(BaseModel):
    """创建路由配置请求模型"""
    name: str = Field(..., description="路由名称", min_length=1, max_length=100)
    description: Optional[str] = Field(None, description="路由描述", max_length=500)
    target_url: str = Field(..., description="目标URL", min_length=1, max_length=500)
    path_prefix: Optional[str] = Field(None, description="路径前缀（用于固定路由）", max_length=200)
    timeout: int = Field(30, description="超时时间（秒）", ge=1, le=300)
    is_active: bool = Field(True, description="是否启用")


class RouteConfigUpdate(BaseModel):
    """更新路由配置请求模型"""
    name: Optional[str] = Field(None, description="路由名称", min_length=1, max_length=100)
    description: Optional[str] = Field(None, description="路由描述", max_length=500)
    target_url: Optional[str] = Field(None, description="目标URL", min_length=1, max_length=500)
    path_prefix: Optional[str] = Field(None, description="路径前缀", max_length=200)
    timeout: Optional[int] = Field(None, description="超时时间（秒）", ge=1, le=300)
    is_active: Optional[bool] = Field(None, description="是否启用")


class RouteConfigResponse(BaseModel):
    """路由配置响应模型"""
    route_id: str
    name: str
    description: Optional[str]
    target_url: str
    path_prefix: Optional[str]
    is_active: bool
    timeout: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


def generate_route_id() -> str:
    """生成路由ID"""
    return f"route_{uuid.uuid4().hex[:12]}" 