"""
审计日志数据模型
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
    return datetime.now(china_tz)
class AuditLogDB(Base):
    """审计日志数据库模型"""
    __tablename__ = "audit_logs"
    
    id = Column(String(50), primary_key=True, index=True)
    request_id = Column(String(50), index=True, nullable=False)
    api_key = Column(String(100), index=True, nullable=True)
    source_path = Column(String(100), index=True, nullable=True)
    method = Column(String(10), nullable=False)
    path = Column(String(500), nullable=False)
    target_url = Column(String(500), nullable=True)
    status_code = Column(Integer, nullable=False)
    response_time_ms = Column(Integer, nullable=False)
    request_size = Column(Integer, default=0)
    response_size = Column(Integer, default=0)
    user_agent = Column(String(500), nullable=True)
    ip_address = Column(String(50), nullable=True)
    error_message = Column(Text, nullable=True)
    
    # 流式响应相关字段
    is_stream = Column(Boolean, default=False, index=True)
    stream_chunks = Column(Integer, default=0)
    
    # 详细审计字段（可选）
    request_headers = Column(Text, nullable=True)
    request_body = Column(Text, nullable=True)
    response_headers = Column(Text, nullable=True)
    response_body = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=get_china_time, index=True)


class AuditLogCreate(BaseModel):
    """创建审计日志请求模型"""
    request_id: str
    api_key: Optional[str] = None
    source_path: Optional[str] = None
    method: str
    path: str
    target_url: Optional[str] = None
    status_code: int
    response_time_ms: int
    request_size: int = 0
    response_size: int = 0
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


class AuditLogResponse(BaseModel):
    """审计日志响应模型"""
    id: str
    request_id: str
    api_key: Optional[str]
    source_path: Optional[str]
    method: str
    path: str
    target_url: Optional[str]
    status_code: int
    response_time_ms: int
    request_size: int
    response_size: int
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