"""
审计日志服务
"""

from datetime import datetime
from typing import List, Optional
from sqlalchemy.orm import Session
from ..models.audit_log import (
    AuditLogDB, AuditLogCreate, AuditLogResponse,
    generate_log_id
)


class AuditService:
    """审计日志服务"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create_log(self, log_data: AuditLogCreate) -> AuditLogResponse:
        """
        创建审计日志
        
        Args:
            log_data: 日志数据
        
        Returns:
            AuditLogResponse: 创建的日志
        """
        # 生成日志ID
        log_id = generate_log_id()
        
        # 创建数据库记录
        db_log = AuditLogDB(
            id=log_id,
            request_id=log_data.request_id,
            api_key=log_data.api_key,
            source_path=log_data.source_path,
            method=log_data.method,
            path=log_data.path,
            target_url=log_data.target_url,
            status_code=log_data.status_code,
            response_time_ms=log_data.response_time_ms,
            request_size=log_data.request_size,
            response_size=log_data.response_size,
            user_agent=log_data.user_agent,
            ip_address=log_data.ip_address,
            error_message=log_data.error_message,
            is_stream=log_data.is_stream,
            stream_chunks=log_data.stream_chunks,
            request_headers=log_data.request_headers,
            request_body=log_data.request_body,
            response_headers=log_data.response_headers,
            response_body=log_data.response_body
        )
        
        self.db.add(db_log)
        self.db.commit()
        self.db.refresh(db_log)
        
        return self._to_response(db_log)
    
    def get_logs(
        self,
        api_key: str = None,
        source_path: str = None,
        method: str = None,
        status_code: int = None,
        start_time: datetime = None,
        end_time: datetime = None,
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
            limit: 限制数量
            offset: 偏移量
        
        Returns:
            List[AuditLogResponse]: 日志列表
        """
        query = self.db.query(AuditLogDB)
        
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
            query = query.filter(AuditLogDB.created_at >= start_time)
        
        if end_time:
            query = query.filter(AuditLogDB.created_at <= end_time)
        
        # 排序和分页
        db_logs = query.order_by(AuditLogDB.created_at.desc()).offset(offset).limit(limit).all()
        
        return [self._to_response(db_log) for db_log in db_logs]
    
    def get_log_by_id(self, log_id: str) -> Optional[AuditLogResponse]:
        """
        根据ID获取日志
        
        Args:
            log_id: 日志ID
        
        Returns:
            AuditLogResponse: 日志信息，不存在则返回 None
        """
        db_log = self.db.query(AuditLogDB).filter(AuditLogDB.id == log_id).first()
        if db_log:
            return self._to_response(db_log)
        return None
    
    def get_log_by_request_id(self, request_id: str) -> Optional[AuditLogResponse]:
        """
        根据请求ID获取日志
        
        Args:
            request_id: 请求ID
        
        Returns:
            AuditLogResponse: 日志信息，不存在则返回 None
        """
        db_log = self.db.query(AuditLogDB).filter(AuditLogDB.request_id == request_id).first()
        if db_log:
            return self._to_response(db_log)
        return None
    
    def get_stats(
        self,
        start_time: datetime = None,
        end_time: datetime = None
    ) -> dict:
        """
        获取统计信息
        
        Args:
            start_time: 开始时间
            end_time: 结束时间
        
        Returns:
            dict: 统计数据
        """
        from sqlalchemy import func, distinct
        
        query = self.db.query(AuditLogDB)
        
        if start_time:
            query = query.filter(AuditLogDB.created_at >= start_time)
        
        if end_time:
            query = query.filter(AuditLogDB.created_at <= end_time)
        
        # 基础统计
        total_requests = query.count()
        
        # 按状态码统计
        status_stats = self.db.query(
            AuditLogDB.status_code,
            func.count(AuditLogDB.id).label('count')
        ).group_by(AuditLogDB.status_code)
        
        if start_time:
            status_stats = status_stats.filter(AuditLogDB.created_at >= start_time)
        if end_time:
            status_stats = status_stats.filter(AuditLogDB.created_at <= end_time)
        
        status_counts = {str(stat.status_code): stat.count for stat in status_stats.all()}
        
        # 按来源路径统计
        source_stats = self.db.query(
            AuditLogDB.source_path,
            func.count(AuditLogDB.id).label('count')
        ).filter(AuditLogDB.source_path.isnot(None)).group_by(AuditLogDB.source_path)
        
        if start_time:
            source_stats = source_stats.filter(AuditLogDB.created_at >= start_time)
        if end_time:
            source_stats = source_stats.filter(AuditLogDB.created_at <= end_time)
        
        source_counts = {stat.source_path: stat.count for stat in source_stats.all()}
        
        # 平均响应时间
        avg_response_time = query.with_entities(
            func.avg(AuditLogDB.response_time_ms)
        ).scalar() or 0
        
        return {
            "total_requests": total_requests,
            "status_counts": status_counts,
            "source_counts": source_counts,
            "avg_response_time_ms": round(float(avg_response_time), 2)
        }
    
    def get_hourly_metrics(self, hours: int = 24) -> List[dict]:
        """
        获取按小时统计的指标数据
        """
        from sqlalchemy import func, extract
        from datetime import datetime, timedelta
        
        # 计算开始时间
        start_time = datetime.utcnow() - timedelta(hours=hours)
        
        # 按小时分组统计 - 总请求数和平均响应时间
        hourly_stats = self.db.query(
            extract('hour', AuditLogDB.created_at).label('hour'),
            func.count(AuditLogDB.id).label('requests'),
            func.avg(AuditLogDB.response_time_ms).label('avg_response_time')
        ).filter(
            AuditLogDB.created_at >= start_time
        ).group_by(
            extract('hour', AuditLogDB.created_at)
        ).all()
        
        # 按小时分组统计 - 成功请求数 (200-299状态码)
        success_stats = self.db.query(
            extract('hour', AuditLogDB.created_at).label('hour'),
            func.count(AuditLogDB.id).label('success_count')
        ).filter(
            AuditLogDB.created_at >= start_time,
            AuditLogDB.status_code >= 200,
            AuditLogDB.status_code < 300
        ).group_by(
            extract('hour', AuditLogDB.created_at)
        ).all()
        
        # 将成功请求数转换为字典，以便快速查找
        success_dict = {int(stat.hour): stat.success_count for stat in success_stats}
        
        # 转换为字典格式
        result = []
        for stat in hourly_stats:
            hour = int(stat.hour)
            total_requests = int(stat.requests)
            success_count = success_dict.get(hour, 0)
            
            # 计算成功率
            success_rate = (success_count / total_requests * 100) if total_requests > 0 else 0
            
            result.append({
                "hour": hour,
                "requests": total_requests,
                "avg_response_time": round(float(stat.avg_response_time or 0), 2),
                "success_rate": round(float(success_rate), 2)
            })
        
        return result
    
    def get_trends_data(self, days: int = 30, group_by: str = "day") -> dict:
        """
        获取趋势数据
        """
        from sqlalchemy import func, extract
        from datetime import datetime, timedelta
        
        # 计算开始时间
        start_time = datetime.utcnow() - timedelta(days=days)
        
        if group_by == "day":
            # 按天分组 - 使用DATE函数
            group_field = func.date(AuditLogDB.created_at)
        else:
            # 按小时分组 - 使用日期截断到小时
            group_field = func.strftime('%Y-%m-%d %H:00:00', AuditLogDB.created_at)
        
        # 按时间分组统计 - 总请求数和平均响应时间
        trends_stats = self.db.query(
            group_field.label('period'),
            func.count(AuditLogDB.id).label('requests'),
            func.avg(AuditLogDB.response_time_ms).label('avg_response_time')
        ).filter(
            AuditLogDB.created_at >= start_time
        ).group_by(
            group_field
        ).order_by(
            group_field
        ).all()
        
        # 按时间分组统计 - 错误请求数 (400+状态码)
        error_stats = self.db.query(
            group_field.label('period'),
            func.count(AuditLogDB.id).label('error_count')
        ).filter(
            AuditLogDB.created_at >= start_time,
            AuditLogDB.status_code >= 400
        ).group_by(
            group_field
        ).all()
        
        # 将错误请求数转换为字典
        error_dict = {str(stat.period): stat.error_count for stat in error_stats}
        
        # 转换为前端需要的格式
        labels = []
        requests = []
        response_time = []
        error_rate = []
        
        for stat in trends_stats:
            period_str = str(stat.period)
            total_requests = int(stat.requests)
            error_count = error_dict.get(period_str, 0)
            
            labels.append(period_str)
            requests.append(total_requests)
            response_time.append(round(float(stat.avg_response_time or 0), 2))
            
            # 计算错误率
            err_rate = (error_count / total_requests * 100) if total_requests > 0 else 0
            error_rate.append(round(float(err_rate), 2))
        
        return {
            "labels": labels,
            "requests": requests,
            "responseTime": response_time,
            "errorRate": error_rate
        }
    
    def _to_response(self, db_log: AuditLogDB) -> AuditLogResponse:
        """
        转换数据库模型到响应模型
        
        Args:
            db_log: 数据库模型
        
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
            response_time_ms=db_log.response_time_ms,
            request_size=db_log.request_size,
            response_size=db_log.response_size,
            user_agent=db_log.user_agent,
            ip_address=db_log.ip_address,
            error_message=db_log.error_message,
            created_at=db_log.created_at,
            is_stream=db_log.is_stream,
            stream_chunks=db_log.stream_chunks,
            request_headers=db_log.request_headers,
            request_body=db_log.request_body,
            response_headers=db_log.response_headers,
            response_body=db_log.response_body
        )
 