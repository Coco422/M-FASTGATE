"""
审计日志服务 - v0.2.0
移除Phase 2.4相关代码，添加first_response_time处理，优化异步处理性能
"""

import asyncio
import json
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from ..models.audit_log import (
    AuditLogDB, AuditLogCreate, AuditLogResponse,
    generate_log_id, generate_request_id
)
from ..database import get_db
from ..config import settings
import structlog

logger = structlog.get_logger(__name__)

# 定义中国时区
china_tz = timezone(timedelta(hours=8))

def get_china_time():
    """获取中国时间"""
    return datetime.now(china_tz)


class AuditService:
    """审计日志服务 - v0.2.0"""
    
    # 配置常量
    MAX_BODY_SIZE = 10240  # 最大请求/响应体大小（字节）
    MAX_HEADER_SIZE = 2048  # 最大请求/响应头大小（字节）
    SENSITIVE_HEADERS = {
        'authorization', 'x-api-key', 'cookie', 'set-cookie', 
        'x-auth-token', 'x-access-token', 'proxy-authorization'
    }
    
    def __init__(self):
        """初始化审计服务"""
        self.logger = logger.bind(service="audit_service")
        self.async_audit = settings.proxy.get('async_audit', True)
        self.audit_full_request = settings.proxy.get('audit_full_request', True)
        self.audit_full_response = settings.proxy.get('audit_full_response', True)
    
    async def log_request_start(self, request_info: Dict[str, Any]) -> str:
        """
        记录请求开始（异步）
        
        Args:
            request_info: 请求信息
            
        Returns:
            str: 日志ID
        """
        if self.async_audit:
            # 异步处理，不阻塞主请求
            asyncio.create_task(self._log_request_start_impl(request_info))
            return request_info.get("request_id", "")
        else:
            return await self._log_request_start_impl(request_info)
    
    async def _log_request_start_impl(self, request_info: Dict[str, Any]) -> str:
        """记录请求开始的实现"""
        try:
            log_id = generate_log_id()
            request_id = request_info.get("request_id") or generate_request_id()
            
            # 创建审计日志记录
            db_log = AuditLogDB(
                id=log_id,
                request_id=request_id,
                api_key=request_info.get("api_key"),
                source_path=request_info.get("source_path"),
                method=request_info.get("method"),
                path=request_info.get("path"),
                target_url=request_info.get("target_url"),
                request_time=request_info.get("request_time", get_china_time()),
                request_size=request_info.get("request_size", 0),
                user_agent=request_info.get("user_agent"),
                ip_address=request_info.get("ip_address"),
                request_headers=self._serialize_headers(request_info.get("request_headers")),
                request_body=self._serialize_body(request_info.get("request_body"))
            )
            
            # 保存到数据库
            db = next(get_db())
            try:
                db.add(db_log)
                db.commit()
            finally:
                db.close()
            
            self.logger.info(
                "Request start logged",
                request_id=request_id,
                log_id=log_id,
                method=request_info.get("method"),
                path=request_info.get("path")
            )
            
            return log_id
            
        except Exception as e:
            self.logger.error(
                "Failed to log request start",
                error=str(e),
                request_id=request_info.get("request_id")
            )
            return ""
    
    async def log_first_response(self, request_id: str, first_response_time: datetime) -> None:
        """
        记录首次响应时间（用于流式响应）
        
        Args:
            request_id: 请求ID
            first_response_time: 首次响应时间
        """
        if self.async_audit:
            asyncio.create_task(self._log_first_response_impl(request_id, first_response_time))
        else:
            await self._log_first_response_impl(request_id, first_response_time)
    
    async def _log_first_response_impl(self, request_id: str, first_response_time: datetime) -> None:
        """记录首次响应时间的实现"""
        try:
            db = next(get_db())
            try:
                audit_log = db.query(AuditLogDB).filter(AuditLogDB.request_id == request_id).first()
                if audit_log:
                    audit_log.first_response_time = first_response_time
                    db.commit()
                    
                    self.logger.debug(
                        "First response time logged",
                        request_id=request_id,
                        first_response_time=first_response_time
                    )
                else:
                    self.logger.warning("Audit log not found for first response", request_id=request_id)
            finally:
                db.close()
                    
        except Exception as e:
            self.logger.error(
                "Failed to log first response time",
                error=str(e),
                request_id=request_id
            )
    
    async def log_request_complete(self, request_id: str, response_info: Dict[str, Any]) -> None:
        """
        记录请求完成
        
        Args:
            request_id: 请求ID
            response_info: 响应信息
        """
        if self.async_audit:
            asyncio.create_task(self._log_request_complete_impl(request_id, response_info))
        else:
            await self._log_request_complete_impl(request_id, response_info)
    
    async def _log_request_complete_impl(self, request_id: str, response_info: Dict[str, Any]) -> None:
        """记录请求完成的实现"""
        try:
            db = next(get_db())
            try:
                audit_log = db.query(AuditLogDB).filter(AuditLogDB.request_id == request_id).first()
                if audit_log:
                    # 更新响应信息
                    audit_log.status_code = response_info.get("status_code")
                    audit_log.response_time = response_info.get("response_time", get_china_time())
                    audit_log.response_size = response_info.get("response_size", 0)
                    audit_log.is_stream = response_info.get("is_stream", False)
                    audit_log.stream_chunks = response_info.get("stream_chunks", 0)
                    audit_log.error_message = response_info.get("error_message")
                    
                    # 计算响应时间（毫秒）
                    if audit_log.request_time and audit_log.response_time:
                        response_time_delta = audit_log.response_time - audit_log.request_time
                        audit_log.response_time_ms = int(response_time_delta.total_seconds() * 1000)
                    
                    # 可选记录响应头和响应体
                    if self.audit_full_response:
                        audit_log.response_headers = self._serialize_headers(response_info.get("response_headers"))
                        audit_log.response_body = self._serialize_body(response_info.get("response_body"))
                    
                    db.commit()
                    
                    self.logger.info(
                        "Request complete logged",
                        request_id=request_id,
                        status_code=response_info.get("status_code"),
                        response_time_ms=audit_log.response_time_ms,
                        is_stream=audit_log.is_stream
                    )
                else:
                    self.logger.warning("Audit log not found for completion", request_id=request_id)
            finally:
                db.close()
                    
        except Exception as e:
            self.logger.error(
                "Failed to log request complete",
                error=str(e),
                request_id=request_id
            )
    
    async def log_stream_chunk(self, request_id: str, chunk_size: int) -> None:
        """
        记录流式响应块信息（增量更新）
        
        Args:
            request_id: 请求ID
            chunk_size: 块大小
        """
        if not self.async_audit:
            return  # 只在异步模式下支持
            
        asyncio.create_task(self._log_stream_chunk_impl(request_id, chunk_size))
    
    async def _log_stream_chunk_impl(self, request_id: str, chunk_size: int) -> None:
        """记录流式响应块的实现"""
        try:
            db = next(get_db())
            try:
                audit_log = db.query(AuditLogDB).filter(AuditLogDB.request_id == request_id).first()
                if audit_log:
                    # 增量更新
                    audit_log.stream_chunks = (audit_log.stream_chunks or 0) + 1
                    audit_log.response_size = (audit_log.response_size or 0) + chunk_size
                    db.commit()
            finally:
                db.close()
                    
        except Exception as e:
            # 流式块记录失败不应该影响主流程，只记录警告
            self.logger.warning(
                "Failed to log stream chunk",
                error=str(e),
                request_id=request_id
            )
    
    def get_logs(
        self,
        api_key: Optional[str] = None,
        source_path: Optional[str] = None,
        method: Optional[str] = None,
        status_code: Optional[int] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        is_stream: Optional[bool] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[AuditLogResponse]:
        """
        查询审计日志
        
        Args:
            api_key: 过滤 API Key
            source_path: 过滤来源路径
            method: 过滤请求方法
            status_code: 过滤状态码
            start_time: 开始时间
            end_time: 结束时间
            is_stream: 过滤流式响应
            limit: 限制数量
            offset: 偏移量
        
        Returns:
            List[AuditLogResponse]: 日志列表
        """
        with get_db() as db:
            query = db.query(AuditLogDB)
            
            # 添加过滤条件
            if api_key:
                query = query.filter(AuditLogDB.api_key == api_key)
            
            if source_path:
                query = query.filter(AuditLogDB.source_path == source_path)
            
            if method:
                query = query.filter(AuditLogDB.method == method)
            
            if status_code:
                query = query.filter(AuditLogDB.status_code == status_code)
            
            if start_time:
                query = query.filter(AuditLogDB.request_time >= start_time)
            
            if end_time:
                query = query.filter(AuditLogDB.request_time <= end_time)
                
            if is_stream is not None:
                query = query.filter(AuditLogDB.is_stream == is_stream)
            
            # 排序和分页
            db_logs = query.order_by(AuditLogDB.request_time.desc()).offset(offset).limit(limit).all()
            
            return [self._to_response(db_log) for db_log in db_logs]
    
    def get_log_by_request_id(self, request_id: str) -> Optional[AuditLogResponse]:
        """
        根据请求ID获取日志
        
        Args:
            request_id: 请求ID
        
        Returns:
            AuditLogResponse: 日志信息，不存在则返回 None
        """
        with get_db() as db:
            db_log = db.query(AuditLogDB).filter(AuditLogDB.request_id == request_id).first()
            if db_log:
                return self._to_response(db_log)
            return None
    
    def get_stats(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        获取统计信息
        
        Args:
            start_time: 开始时间
            end_time: 结束时间
        
        Returns:
            Dict[str, Any]: 统计数据
        """
        from sqlalchemy import func
        
        with get_db() as db:
            query = db.query(AuditLogDB)
            
            if start_time:
                query = query.filter(AuditLogDB.request_time >= start_time)
            
            if end_time:
                query = query.filter(AuditLogDB.request_time <= end_time)
            
            # 基础统计
            total_requests = query.count()
            
            # 按状态码统计
            status_stats = db.query(
                AuditLogDB.status_code,
                func.count(AuditLogDB.id).label('count')
            )
            
            if start_time:
                status_stats = status_stats.filter(AuditLogDB.request_time >= start_time)
            if end_time:
                status_stats = status_stats.filter(AuditLogDB.request_time <= end_time)
            
            status_stats = status_stats.group_by(AuditLogDB.status_code)
            status_counts = {str(stat.status_code) if stat.status_code else 'null': stat.count for stat in status_stats.all()}
            
            # 流式响应统计
            stream_count = query.filter(AuditLogDB.is_stream == True).count()
            
            # 平均响应时间
            avg_response_time = db.query(func.avg(AuditLogDB.response_time_ms)).scalar() or 0
            
            return {
                "total_requests": total_requests,
                "status_counts": status_counts,
                "stream_requests": stream_count,
                "avg_response_time_ms": round(avg_response_time, 2),
                "period": {
                    "start_time": start_time.isoformat() if start_time else None,
                    "end_time": end_time.isoformat() if end_time else None
                }
            }
    
    def _serialize_headers(self, headers: Optional[Dict[str, str]]) -> Optional[str]:
        """
        序列化请求头（移除敏感信息并限制大小）
        
        Args:
            headers: 请求头字典
            
        Returns:
            Optional[str]: JSON字符串或None
        """
        if not headers or not self.audit_full_request:
            return None
        
        try:
            # 移除敏感头部
            sanitized = {}
            for key, value in headers.items():
                if key.lower() not in self.SENSITIVE_HEADERS:
                    sanitized[key] = value
                else:
                    sanitized[key] = "[REDACTED]"
            
            json_str = json.dumps(sanitized, ensure_ascii=False)
            
            # 限制大小
            if len(json_str) > self.MAX_HEADER_SIZE:
                return json_str[:self.MAX_HEADER_SIZE] + "...[TRUNCATED]"
            
            return json_str
            
        except Exception as e:
            self.logger.warning("Failed to serialize headers", error=str(e))
            return None
    
    def _serialize_body(self, body: Optional[Any]) -> Optional[str]:
        """
        序列化请求/响应体（限制大小）
        
        Args:
            body: 请求/响应体
            
        Returns:
            Optional[str]: JSON字符串或None
        """
        if body is None or not self.audit_full_request:
            return None
        
        try:
            if isinstance(body, (dict, list)):
                json_str = json.dumps(body, ensure_ascii=False)
            elif isinstance(body, str):
                json_str = body
            else:
                json_str = str(body)
            
            # 限制大小
            if len(json_str) > self.MAX_BODY_SIZE:
                return json_str[:self.MAX_BODY_SIZE] + "...[TRUNCATED]"
            
            return json_str
            
        except Exception as e:
            self.logger.warning("Failed to serialize body", error=str(e))
            return None
    
    def _to_response(self, db_log: AuditLogDB) -> AuditLogResponse:
        """
        转换数据库记录为响应模型
        
        Args:
            db_log: 数据库记录
            
        Returns:
            AuditLogResponse: 响应模型
        """
        return AuditLogResponse(
            id=db_log.id,
            request_id=db_log.request_id,
            api_key=db_log.api_key,
            source_path=db_log.source_path,
            method=db_log.method,
            path=db_log.path,
            target_url=db_log.target_url,
            status_code=db_log.status_code,
            request_time=db_log.request_time,
            first_response_time=db_log.first_response_time,
            response_time=db_log.response_time,
            response_time_ms=db_log.response_time_ms,
            request_size=db_log.request_size,
            response_size=db_log.response_size,
            user_agent=db_log.user_agent,
            ip_address=db_log.ip_address,
            is_stream=db_log.is_stream,
            stream_chunks=db_log.stream_chunks,
            error_message=db_log.error_message,
            request_headers=db_log.request_headers,
            request_body=db_log.request_body,
            response_headers=db_log.response_headers,
            response_body=db_log.response_body,
            created_at=db_log.created_at
        )
 