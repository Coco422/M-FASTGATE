"""
API Key 数据模型
"""

from datetime import datetime, timedelta
from typing import List, Optional
from sqlalchemy import Column, String, DateTime, Boolean, Integer, Text
from sqlalchemy.sql import func
from pydantic import BaseModel
from ..database import Base
from ..config import settings
import uuid
import secrets


class APIKeyDB(Base):
    """API Key 数据库模型"""
    __tablename__ = "api_keys"
    
    key_id = Column(String(50), primary_key=True, index=True)
    key_value = Column(String(100), unique=True, index=True, nullable=False)
    source_path = Column(String(100), nullable=False, index=True)
    permissions = Column(Text, default="[]")  # JSON 字符串存储权限列表
    created_at = Column(DateTime, default=func.now())
    expires_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True, index=True)
    usage_count = Column(Integer, default=0)
    rate_limit = Column(Integer, nullable=True)
    last_used_at = Column(DateTime, nullable=True)


class APIKeyCreate(BaseModel):
    """创建 API Key 请求模型"""
    source_path: str
    permissions: List[str] = []
    expires_days: Optional[int] = None
    rate_limit: Optional[int] = None


class APIKeyUpdate(BaseModel):
    """更新 API Key 请求模型"""
    source_path: Optional[str] = None
    permissions: Optional[List[str]] = None
    expires_at: Optional[datetime] = None
    is_active: Optional[bool] = None
    rate_limit: Optional[int] = None


class APIKeyResponse(BaseModel):
    """API Key 响应模型"""
    key_id: str
    key_value: str
    source_path: str
    permissions: List[str]
    created_at: datetime
    expires_at: Optional[datetime]
    is_active: bool
    usage_count: int
    rate_limit: Optional[int]
    last_used_at: Optional[datetime]
    
    class Config:
        from_attributes = True


def generate_api_key() -> tuple[str, str]:
    """
    生成 API Key
    
    Returns:
        tuple: (key_id, key_value)
    """
    key_id = f"{settings.security.key_prefix}{uuid.uuid4().hex[:12]}"
    key_value = f"{settings.security.key_prefix}{secrets.token_urlsafe(32)}"
    return key_id, key_value


def calculate_expires_at(days: int = None) -> datetime:
    """
    计算过期时间
    
    Args:
        days: 有效天数，默认使用配置值
    
    Returns:
        datetime: 过期时间
    """
    if days is None:
        days = settings.security.default_expiry_days
    
    return datetime.utcnow() + timedelta(days=days) 