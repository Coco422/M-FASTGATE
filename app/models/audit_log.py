"""
审计日志数据模型 - v0.2.0
"""

from datetime import datetime, timezone, timedelta
from typing import Optional
from sqlalchemy import Column, String, DateTime, Integer, Text, Boolean
from sqlalchemy.sql import func
from pydantic import BaseModel
from ..database import Base
import uuid

# 定义中国时区
china_tz = timezone(timedelta(hours=8))

def get_china_time():
    """获取中国时间"""
    return datetime.now(china_tz)

class AuditLogDB(Base):
    """审计日志数据库模型"""
    __tablename__ = "audit_logs"
    
    id = Column(String(50), primary_key=True, index=True)
    request_id = Column(String(50), index=True, nullable=False)
    api_key = Column(String(100), index=True, nullable=True)
    source_path = Column(String(100), index=True, nullable=True)
    method = Column(String(10), nullable=False)
    path = Column(String(500), nullable=False, index=True)
    target_url = Column(String(500), nullable=True)
    status_code = Column(Integer, nullable=True)
    
    # 时间相关字段
    request_time = Column(DateTime, nullable=False, index=True)
    first_response_time = Column(DateTime, nullable=True)  # 新增：首个字节返回时间
    response_time = Column(DateTime, nullable=True)
    response_time_ms = Column(Integer, nullable=True)
    
    # 大小相关字段
    request_size = Column(Integer, default=0)
    response_size = Column(Integer, default=0)
    
    # 请求信息字段
    user_agent = Column(String(500), nullable=True)
    ip_address = Column(String(50), nullable=True, index=True)
    error_message = Column(Text, nullable=True)
    
    # 流式响应相关字段
    is_stream = Column(Boolean, default=False, index=True)
    stream_chunks = Column(Integer, default=0)
    
    # 详细审计字段（可选）
    request_headers = Column(Text, nullable=True)
    request_body = Column(Text, nullable=True)
    response_headers = Column(Text, nullable=True)
    response_body = Column(Text, nullable=True)
    
    # 创建时间（中国时区）
    created_at = Column(DateTime, default=get_china_time, index=True)


class AuditLogCreate(BaseModel):
    """创建审计日志请求模型"""
    request_id: str
    api_key: Optional[str] = None
    source_path: Optional[str] = None
    method: str
    path: str
    target_url: Optional[str] = None
    status_code: Optional[int] = None
    
    # 时间相关字段
    request_time: datetime
    first_response_time: Optional[datetime] = None
    response_time: Optional[datetime] = None
    response_time_ms: Optional[int] = None
    
    # 大小相关字段
    request_size: int = 0
    response_size: int = 0
    
    # 请求信息字段
    user_agent: Optional[str] = None
    ip_address: Optional[str] = None
    error_message: Optional[str] = None
    
    # 流式响应相关
    is_stream: bool = False
    stream_chunks: int = 0
    
    # 详细审计（可选）
    request_headers: Optional[str] = None
    request_body: Optional[str] = None
    response_headers: Optional[str] = None
    response_body: Optional[str] = None
    

class AuditLogUpdate(BaseModel):
    """更新审计日志请求模型（用于流式响应更新）"""
    first_response_time: Optional[datetime] = None
    response_time: Optional[datetime] = None
    response_time_ms: Optional[int] = None
    status_code: Optional[int] = None
    response_size: Optional[int] = None
    stream_chunks: Optional[int] = None
    error_message: Optional[str] = None
    response_headers: Optional[str] = None
    response_body: Optional[str] = None


class AuditLogResponse(BaseModel):
    """审计日志响应模型"""
    id: str
    request_id: str
    api_key: Optional[str] = None
    api_key_source_path: Optional[str] = None
    source_path: Optional[str] = None
    method: Optional[str] = None
    path: Optional[str] = None
    target_url: Optional[str] = None
    status_code: Optional[int] = None
    
    # 时间相关字段
    request_time: datetime
    first_response_time: Optional[datetime]
    response_time: Optional[datetime]
    response_time_ms: Optional[int]
    
    # 大小相关字段
    request_size: int
    response_size: int
    
    # 请求信息字段
    user_agent: Optional[str]
    ip_address: Optional[str]
    error_message: Optional[str]
    
    # 流式响应相关
    is_stream: bool
    stream_chunks: int
    
    # 详细审计
    request_headers: Optional[str]
    request_body: Optional[str]
    response_headers: Optional[str] 
    response_body: Optional[str]
    
    created_at: datetime
    
    class Config:
        from_attributes = True


class AuditLogQuery(BaseModel):
    """审计日志查询模型"""
    api_key: Optional[str] = None
    path: Optional[str] = None
    method: Optional[str] = None
    status_code: Optional[int] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    is_stream: Optional[bool] = None
    has_error: Optional[bool] = None
    limit: int = 100
    offset: int = 0


def generate_request_id() -> str:
    """
    生成请求ID
    
    Returns:
        str: 请求ID
    """
    return f"req_{uuid.uuid4().hex[:12]}"


def generate_log_id() -> str:
    """
    生成日志ID
    
    Returns:
        str: 日志ID
    """
    return f"log_{uuid.uuid4().hex[:12]}" 