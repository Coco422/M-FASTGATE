"""
通用代理路由数据模型 - v0.2.0
"""

from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from sqlalchemy import Column, String, DateTime, Integer, Text, Boolean
from pydantic import BaseModel, Field
from ..database import Base
import uuid
import json

# 定义中国时区
china_tz = timezone(timedelta(hours=8))

def get_china_time():
    """获取中国时间"""
    return datetime.now(china_tz)

class ProxyRouteDB(Base):
    """代理路由数据库模型"""
    __tablename__ = "proxy_routes"
    
    route_id = Column(String(50), primary_key=True, index=True)
    route_name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    
    # 匹配规则
    match_path = Column(String(500), nullable=False, index=True)
    match_method = Column(String(20), default='ANY')
    match_headers = Column(Text, nullable=True)  # JSON字符串
    match_body_schema = Column(Text, nullable=True)  # JSON Schema字符串
    
    # 目标配置
    target_host = Column(String(200), nullable=False)
    target_path = Column(String(500), nullable=False)
    target_protocol = Column(String(10), default='http')
    
    # 转换规则
    strip_path_prefix = Column(Boolean, default=False)
    add_headers = Column(Text, nullable=True)  # JSON字符串
    add_body_fields = Column(Text, nullable=True)  # JSON字符串
    remove_headers = Column(Text, nullable=True)  # JSON数组字符串
    
    # 其他配置
    timeout = Column(Integer, default=30)
    retry_count = Column(Integer, default=0)
    is_active = Column(Boolean, default=True, index=True)
    priority = Column(Integer, default=100, index=True)  # 数字越小优先级越高
    
    # 时间戳（中国时区）
    created_at = Column(DateTime, default=get_china_time, index=True)
    updated_at = Column(DateTime, default=get_china_time, onupdate=get_china_time)


class ProxyRouteCreate(BaseModel):
    """创建代理路由请求模型"""
    route_name: str = Field(..., min_length=1, max_length=100, description="路由名称")
    description: Optional[str] = Field(None, description="路由描述")
    
    # 匹配规则
    match_path: str = Field(..., description="匹配路径模式，如：/v1/*, /api/**")
    match_method: str = Field(default='ANY', description="匹配HTTP方法：GET,POST,PUT,DELETE,ANY")
    match_headers: Optional[Dict[str, str]] = Field(None, description="匹配请求头条件")
    match_body_schema: Optional[Dict[str, Any]] = Field(None, description="匹配请求体结构")
    
    # 目标配置
    target_host: str = Field(..., description="目标主机，如：172.16.99.204:3398")
    target_path: str = Field(..., description="目标路径，如：/v1/chat/completions")
    target_protocol: str = Field(default='http', description="协议：http/https")
    
    # 转换规则
    strip_path_prefix: bool = Field(default=False, description="是否剔除路径前缀")
    add_headers: Optional[Dict[str, str]] = Field(None, description="新增请求头")
    add_body_fields: Optional[Dict[str, Any]] = Field(None, description="新增请求体字段")
    remove_headers: Optional[List[str]] = Field(None, description="移除请求头列表")
    
    # 其他配置
    timeout: int = Field(default=30, ge=1, le=300, description="超时时间（秒）")
    retry_count: int = Field(default=0, ge=0, le=5, description="重试次数")
    is_active: bool = Field(default=True, description="是否启用")
    priority: int = Field(default=100, ge=1, le=1000, description="优先级（数字越小优先级越高）")


class ProxyRouteUpdate(BaseModel):
    """更新代理路由请求模型"""
    route_name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    
    # 匹配规则
    match_path: Optional[str] = None
    match_method: Optional[str] = None
    match_headers: Optional[Dict[str, str]] = None
    match_body_schema: Optional[Dict[str, Any]] = None
    
    # 目标配置
    target_host: Optional[str] = None
    target_path: Optional[str] = None
    target_protocol: Optional[str] = None
    
    # 转换规则
    strip_path_prefix: Optional[bool] = None
    add_headers: Optional[Dict[str, str]] = None
    add_body_fields: Optional[Dict[str, Any]] = None
    remove_headers: Optional[List[str]] = None
    
    # 其他配置
    timeout: Optional[int] = Field(None, ge=1, le=300)
    retry_count: Optional[int] = Field(None, ge=0, le=5)
    is_active: Optional[bool] = None
    priority: Optional[int] = Field(None, ge=1, le=1000)


class ProxyRouteResponse(BaseModel):
    """代理路由响应模型"""
    route_id: str
    route_name: str
    description: Optional[str]
    
    # 匹配规则
    match_path: str
    match_method: str
    match_headers: Optional[Dict[str, str]]
    match_body_schema: Optional[Dict[str, Any]]
    
    # 目标配置
    target_host: str
    target_path: str
    target_protocol: str
    
    # 转换规则
    strip_path_prefix: bool
    add_headers: Optional[Dict[str, str]]
    add_body_fields: Optional[Dict[str, Any]]
    remove_headers: Optional[List[str]]
    
    # 其他配置
    timeout: int
    retry_count: int
    is_active: bool
    priority: int
    
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class ProxyRouteQuery(BaseModel):
    """代理路由查询模型"""
    route_name: Optional[str] = None
    match_path: Optional[str] = None
    target_host: Optional[str] = None
    is_active: Optional[bool] = None
    limit: int = Field(default=100, ge=1, le=1000)
    offset: int = Field(default=0, ge=0)
    order_by: str = Field(default='priority', description="排序字段：priority,created_at,route_name")
    order_desc: bool = Field(default=False, description="是否降序")


def generate_route_id() -> str:
    """
    生成路由ID
    
    Returns:
        str: 路由ID
    """
    return f"route_{uuid.uuid4().hex[:12]}"


def json_to_dict(json_str: Optional[str]) -> Optional[Dict]:
    """
    将JSON字符串转换为字典
    
    Args:
        json_str: JSON字符串
        
    Returns:
        字典或None
    """
    if not json_str:
        return None
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        return None


def dict_to_json(data: Optional[Dict]) -> Optional[str]:
    """
    将字典转换为JSON字符串
    
    Args:
        data: 字典数据
        
    Returns:
        JSON字符串或None
    """
    if not data:
        return None
    try:
        return json.dumps(data, ensure_ascii=False)
    except (TypeError, ValueError):
        return None


def list_to_json(data: Optional[List]) -> Optional[str]:
    """
    将列表转换为JSON字符串
    
    Args:
        data: 列表数据
        
    Returns:
        JSON字符串或None
    """
    if not data:
        return None
    try:
        return json.dumps(data, ensure_ascii=False)
    except (TypeError, ValueError):
        return None 