"""
M-FastGate v0.2.0 管理接口
"""

from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from ..database import get_db
from ..middleware.auth import verify_admin_token
from ..services.key_manager import KeyManager
from ..services.audit_service import AuditService
from ..models.api_key import APIKeyCreate, APIKeyUpdate, APIKeyResponse
from ..models.proxy_route import ProxyRouteCreate, ProxyRouteDB, ProxyRouteUpdate, ProxyRouteResponse
from ..models.audit_log import AuditLogResponse
from ..config import settings

router = APIRouter()


# ============= API Key 管理 =============

@router.post("/keys")
async def create_api_key(
    key_data: APIKeyCreate,
    db: Session = Depends(get_db),
    token: str = Depends(verify_admin_token)
) -> APIKeyResponse:
    """
    创建新的 API Key
    """
    key_manager = KeyManager(db)
    return key_manager.create_key(key_data)


@router.get("/keys")
async def list_api_keys(
    skip: int = Query(0, ge=0, description="跳过的记录数"),
    limit: int = Query(100, ge=1, le=1000, description="返回的记录数"),
    source_path: Optional[str] = Query(None, description="按来源路径过滤"),
    is_active: Optional[bool] = Query(None, description="按活跃状态过滤"),
    db: Session = Depends(get_db),
    token: str = Depends(verify_admin_token)
) -> List[APIKeyResponse]:
    """
    获取 API Key 列表
    """
    key_manager = KeyManager(db)
    return key_manager.list_keys(skip=skip, limit=limit, source_path=source_path, is_active=is_active)


@router.get("/keys/sources")
async def list_key_sources(
    db: Session = Depends(get_db),
    token: str = Depends(verify_admin_token)
) -> List[str]:
    """
    获取所有唯一的 API Key 来源路径
    """
    from ..models.api_key import APIKeyDB
    sources = db.query(APIKeyDB.source_path).distinct().all()
    return [source[0] for source in sources if source[0]]


@router.get("/keys/{key_id}")
async def get_api_key(
    key_id: str,
    db: Session = Depends(get_db),
    token: str = Depends(verify_admin_token)
) -> APIKeyResponse:
    """
    获取 API Key 详情
    """
    key_manager = KeyManager(db)
    api_key = key_manager.get_key(key_id)
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API Key not found"
        )
    return api_key


@router.post("/keys/update/{key_id}")
async def update_api_key(
    key_id: str,
    key_data: APIKeyUpdate,
    db: Session = Depends(get_db),
    token: str = Depends(verify_admin_token)
) -> APIKeyResponse:
    """
    更新 API Key
    """
    key_manager = KeyManager(db)
    api_key = key_manager.update_key(key_id, key_data)
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API Key not found"
        )
    return api_key


@router.post("/keys/delete/{key_id}")
async def delete_api_key(
    key_id: str,
    db: Session = Depends(get_db),
    token: str = Depends(verify_admin_token)
):
    """
    删除 API Key
    """
    key_manager = KeyManager(db)
    success = key_manager.delete_key(key_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API Key not found"
        )
    return {"message": "API Key deleted successfully"}


# ============= 代理路由管理 =============

@router.post("/routes")
async def create_proxy_route(
    route_data: ProxyRouteCreate,
    db: Session = Depends(get_db),
    token: str = Depends(verify_admin_token)
) -> ProxyRouteResponse:
    """
    创建新的代理路由配置
    """
    from ..models.proxy_route import ProxyRouteDB, dict_to_json, list_to_json
    import uuid
    import json
    
    # 生成路由ID
    route_id = route_data.route_name.lower().replace(" ", "-").replace("_", "-")
    if db.query(ProxyRouteDB).filter(ProxyRouteDB.route_id == route_id).first():
        route_id = f"{route_id}-{uuid.uuid4().hex[:8]}"
    
    # 将Pydantic模型数据转换为数据库存储格式
    route_dict = route_data.dict()
    
    # 转换JSON字段为字符串存储
    db_data = {
        "route_id": route_id,
        "route_name": route_dict["route_name"],
        "description": route_dict.get("description"),
        "match_path": route_dict["match_path"],
        "match_method": route_dict["match_method"],
        "match_headers": dict_to_json(route_dict.get("match_headers")),
        "match_body_schema": dict_to_json(route_dict.get("match_body_schema")),
        "target_host": route_dict["target_host"],
        "target_path": route_dict["target_path"],
        "target_protocol": route_dict["target_protocol"],
        "strip_path_prefix": route_dict["strip_path_prefix"],
        "add_headers": dict_to_json(route_dict.get("add_headers")),
        "add_body_fields": dict_to_json(route_dict.get("add_body_fields")),
        "remove_headers": list_to_json(route_dict.get("remove_headers")),
        "timeout": route_dict["timeout"],
        "retry_count": route_dict["retry_count"],
        "is_active": route_dict["is_active"],
        "priority": route_dict["priority"],
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }
    
    # 创建代理路由
    db_route = ProxyRouteDB(**db_data)
    db.add(db_route)
    db.commit()
    db.refresh(db_route)
    
    # 转换为响应格式
    return convert_db_route_to_response(db_route)


@router.get("/routes")
async def list_proxy_routes(
    skip: int = Query(0, ge=0, description="跳过的记录数"),
    limit: int = Query(100, ge=1, le=1000, description="返回的记录数"),
    is_active: Optional[bool] = Query(None, description="按活跃状态过滤"),
    db: Session = Depends(get_db),
    token: str = Depends(verify_admin_token)
) -> List[ProxyRouteResponse]:
    """
    获取代理路由配置列表
    """
    from ..models.proxy_route import ProxyRouteDB
    
    query = db.query(ProxyRouteDB)
    
    if is_active is not None:
        query = query.filter(ProxyRouteDB.is_active == is_active)
    
    routes = query.order_by(ProxyRouteDB.priority.asc()).offset(skip).limit(limit).all()
    return [convert_db_route_to_response(route) for route in routes]


@router.get("/routes/{route_id}")
async def get_proxy_route(
    route_id: str,
    db: Session = Depends(get_db),
    token: str = Depends(verify_admin_token)
) -> ProxyRouteResponse:
    """
    获取单个代理路由配置详情
    """
    from ..models.proxy_route import ProxyRouteDB
    
    route = db.query(ProxyRouteDB).filter(ProxyRouteDB.route_id == route_id).first()
    if not route:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Proxy route not found"
        )
    return convert_db_route_to_response(route)


@router.post("/routes/update/{route_id}")
async def update_proxy_route(
    route_id: str,
    route_data: ProxyRouteUpdate,
    db: Session = Depends(get_db),
    token: str = Depends(verify_admin_token)
) -> ProxyRouteResponse:
    """
    更新代理路由配置
    """
    from ..models.proxy_route import ProxyRouteDB, dict_to_json, list_to_json
    
    route = db.query(ProxyRouteDB).filter(ProxyRouteDB.route_id == route_id).first()
    if not route:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Proxy route not found"
        )
    
    # 获取更新数据并转换JSON字段
    update_data = route_data.dict(exclude_unset=True)
    
    for field, value in update_data.items():
        if field in ["match_headers", "add_headers", "match_body_schema", "add_body_fields"]:
            # 字典类型字段转换为JSON字符串
            setattr(route, field, dict_to_json(value) if value is not None else None)
        elif field == "remove_headers":
            # 列表类型字段转换为JSON字符串
            setattr(route, field, list_to_json(value) if value is not None else None)
        else:
            # 其他字段直接设置
            setattr(route, field, value)
    
    route.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(route)
    
    return convert_db_route_to_response(route)


def convert_db_route_to_response(db_route: 'ProxyRouteDB') -> ProxyRouteResponse:
    """
    将数据库路由对象转换为API响应对象
    """
    from ..models.proxy_route import json_to_dict
    import json
    
    def safe_json_parse(json_str, default=None):
        """安全解析JSON字符串"""
        if not json_str:
            return default
        try:
            return json.loads(json_str)
        except (json.JSONDecodeError, TypeError):
            return default
    
    return ProxyRouteResponse(
        route_id=db_route.route_id,
        route_name=db_route.route_name,
        description=db_route.description,
        match_path=db_route.match_path,
        match_method=db_route.match_method,
        match_headers=safe_json_parse(db_route.match_headers),
        match_body_schema=safe_json_parse(db_route.match_body_schema),
        target_host=db_route.target_host,
        target_path=db_route.target_path,
        target_protocol=db_route.target_protocol,
        strip_path_prefix=db_route.strip_path_prefix,
        add_headers=safe_json_parse(db_route.add_headers),
        add_body_fields=safe_json_parse(db_route.add_body_fields),
        remove_headers=safe_json_parse(db_route.remove_headers, []),
        timeout=db_route.timeout,
        retry_count=db_route.retry_count,
        is_active=db_route.is_active,
        priority=db_route.priority,
        created_at=db_route.created_at,
        updated_at=db_route.updated_at
    )


@router.post("/routes/delete/{route_id}")
async def delete_proxy_route(
    route_id: str,
    db: Session = Depends(get_db),
    token: str = Depends(verify_admin_token)
):
    """
    删除代理路由配置
    """
    from ..models.proxy_route import ProxyRouteDB
    
    route = db.query(ProxyRouteDB).filter(ProxyRouteDB.route_id == route_id).first()
    if not route:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Proxy route not found"
        )
    
    db.delete(route)
    db.commit()
    
    return {"message": "Proxy route deleted successfully"}


@router.post("/routes/{route_id}/toggle")
async def toggle_proxy_route(
    route_id: str,
    toggle_data: dict,
    db: Session = Depends(get_db),
    token: str = Depends(verify_admin_token)
):
    """
    切换代理路由启用/禁用状态
    """
    from ..models.proxy_route import ProxyRouteDB
    
    route = db.query(ProxyRouteDB).filter(ProxyRouteDB.route_id == route_id).first()
    if not route:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Proxy route not found"
        )
    
    route.is_active = toggle_data.get("is_active", route.is_active)
    route.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(route)
    
    return {"message": f"Route {'enabled' if route.is_active else 'disabled'} successfully"}


@router.post("/routes/{route_id}/test")
async def test_proxy_route(
    route_id: str,
    test_data: dict,
    db: Session = Depends(get_db),
    token: str = Depends(verify_admin_token)
):
    """
    测试代理路由配置
    """
    from ..models.proxy_route import ProxyRouteDB
    from ..services.route_matcher import RouteMatcher
    from ..services.proxy_engine import ProxyEngine
    import httpx
    import time
    
    route = db.query(ProxyRouteDB).filter(ProxyRouteDB.route_id == route_id).first()
    if not route:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Proxy route not found"
        )
    
    # 模拟测试请求
    test_method = test_data.get("test_method", "POST")
    test_headers = test_data.get("test_headers", {})
    test_body = test_data.get("test_body", {})
    timeout = test_data.get("timeout", 10)
    
    # 检查路由匹配
    route_matcher = RouteMatcher()
    
    # 构建测试请求信息
    test_request = {
        "path": route.match_path.replace("*", "test"),
        "method": test_method,
        "headers": test_headers,
        "body": test_body
    }
    
    # 构建路由配置列表
    route_config = {
        "route_id": route.route_id,
        "route_name": route.route_name,
        "match_path": route.match_path,
        "match_method": route.match_method,
        "match_headers": route.match_headers,
        "match_body_schema": route.match_body_schema,
        "is_active": route.is_active,
        "priority": route.priority
    }
    
    matched_route = route_matcher.find_matching_route(test_request, [route_config])
    
    # 构建目标URL
    target_url = f"{route.target_protocol}://{route.target_host}{route.target_path}"
    
    # 执行测试请求
    test_result = {
        "success": False,
        "matched": matched_route is not None and matched_route["route_id"] == route_id,
        "target_url": target_url,
        "response_time_ms": 0,
        "status_code": None,
        "error_message": None,
        "test_result": {
            "request_sent": False,
            "response_received": False,
            "headers_applied": False,
            "body_modified": False
        }
    }
    
    try:
        start_time = time.time()
        
        # 应用请求头转换
        processed_headers = test_headers.copy()
        if route.add_headers:
            import json
            add_headers = json.loads(route.add_headers) if isinstance(route.add_headers, str) else route.add_headers
            processed_headers.update(add_headers)
            test_result["test_result"]["headers_applied"] = True
        
        # 应用请求体转换
        processed_body = test_body.copy()
        if route.add_body_fields:
            import json
            add_body_fields = json.loads(route.add_body_fields) if isinstance(route.add_body_fields, str) else route.add_body_fields
            processed_body.update(add_body_fields)
            test_result["test_result"]["body_modified"] = True
        
        # 发送测试请求
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.request(
                method=test_method,
                url=target_url,
                headers=processed_headers,
                json=processed_body if processed_body else None
            )
            
            test_result["test_result"]["request_sent"] = True
            test_result["test_result"]["response_received"] = True
            test_result["status_code"] = response.status_code
            test_result["success"] = response.status_code < 400
            
        end_time = time.time()
        test_result["response_time_ms"] = round((end_time - start_time) * 1000, 2)
        
    except httpx.TimeoutException:
        test_result["error_message"] = "Request timeout"
        test_result["test_result"]["request_sent"] = True
    except httpx.ConnectError:
        test_result["error_message"] = "Connection failed - target server unreachable"
        test_result["test_result"]["request_sent"] = True
    except Exception as e:
        test_result["error_message"] = str(e)
    
    return test_result


# ============= 审计日志 =============

@router.get("/logs")
async def get_audit_logs(
    skip: int = Query(0, ge=0, description="跳过的记录数"),
    limit: int = Query(50, ge=1, le=10000, description="返回的记录数"),
    api_key: Optional[str] = Query(None, description="按 API Key 过滤"),
    caller: Optional[str] = Query(None, description="按调用者名称过滤"),
    source_path: Optional[str] = Query(None, description="按来源路径过滤"),
    method: Optional[str] = Query(None, description="按请求方法过滤"),
    path: Optional[str] = Query(None, description="按请求路径过滤"),
    status_code: Optional[int] = Query(None, description="按状态码过滤"),
    start_time: Optional[str] = Query(None, description="开始时间过滤（ISO格式）"),
    end_time: Optional[str] = Query(None, description="结束时间过滤（ISO格式）"),
    is_stream: Optional[bool] = Query(None, description="按流式响应过滤"),
    db: Session = Depends(get_db),
    token: str = Depends(verify_admin_token)
):
    """
    获取审计日志
    """
    audit_service = AuditService()
    return audit_service.get_logs(
        offset=skip, 
        limit=limit,
        api_key=api_key,
        caller=caller,
        source_path=source_path,
        method=method,
        status_code=status_code,
        start_time=start_time,
        end_time=end_time,
        is_stream=is_stream
    )


@router.get("/logs/export")
async def export_audit_logs(
    format: str = Query("csv", regex="^(csv|json|xlsx)$", description="导出格式"),
    include_headers: bool = Query(False, description="是否包含请求/响应头"),
    include_body: bool = Query(False, description="是否包含请求/响应体"),
    api_key: Optional[str] = Query(None, description="按 API Key 过滤"),
    source_path: Optional[str] = Query(None, description="按来源路径过滤"),
    method: Optional[str] = Query(None, description="按请求方法过滤"),
    path: Optional[str] = Query(None, description="按请求路径过滤"),
    status_code: Optional[int] = Query(None, description="按状态码过滤"),
    start_time: Optional[str] = Query(None, description="开始时间过滤（ISO格式）"),
    end_time: Optional[str] = Query(None, description="结束时间过滤（ISO格式）"),
    db: Session = Depends(get_db),
    token: str = Depends(verify_admin_token)
):
    """
    导出审计日志
    """
    from fastapi.responses import StreamingResponse
    import io
    import csv
    import json
    
    audit_service = AuditService()
    logs = audit_service.get_logs(
        offset=0,
        limit=10000,  # 最多导出10000条记录
        api_key=api_key,
        source_path=source_path,
        method=method,
        status_code=status_code,
        start_time=start_time,
        end_time=end_time
    )
    
    if format == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        
        # 写入表头
        headers = ["id", "request_id", "api_key", "source_path", "method", "path", 
                  "target_url", "status_code", "request_time", "response_time", 
                  "response_time_ms", "request_size", "response_size", "user_agent", 
                  "ip_address", "error_message", "is_stream", "stream_chunks"]
        
        if include_headers:
            headers.extend(["request_headers", "response_headers"])
        if include_body:
            headers.extend(["request_body", "response_body"])
            
        writer.writerow(headers)
        
        # 写入数据
        for log in logs:
            row = [
                log.get("id"), log.get("request_id"), log.get("api_key"), 
                log.get("source_path"), log.get("method"), log.get("path"),
                log.get("target_url"), log.get("status_code"), log.get("request_time"),
                log.get("response_time"), log.get("response_time_ms"), 
                log.get("request_size"), log.get("response_size"), log.get("user_agent"),
                log.get("ip_address"), log.get("error_message"), log.get("is_stream"),
                log.get("stream_chunks")
            ]
            
            if include_headers:
                row.extend([log.get("request_headers"), log.get("response_headers")])
            if include_body:
                row.extend([log.get("request_body"), log.get("response_body")])
                
            writer.writerow(row)
        
        output.seek(0)
        return StreamingResponse(
            io.BytesIO(output.getvalue().encode("utf-8")),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=audit_logs.csv"}
        )
    
    elif format == "json":
        return StreamingResponse(
            io.BytesIO(json.dumps(logs, ensure_ascii=False, indent=2).encode("utf-8")),
            media_type="application/json",
            headers={"Content-Disposition": "attachment; filename=audit_logs.json"}
        )
    
    else:  # xlsx format
        # 这里可以添加Excel导出逻辑
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Excel export not implemented yet"
        )


@router.get("/logs/{log_id}")
async def get_audit_log(
    log_id: str,
    db: Session = Depends(get_db),
    token: str = Depends(verify_admin_token)
):
    """
    获取单条审计日志详情
    """
    from ..models.audit_log import AuditLogDB
    
    db_log = db.query(AuditLogDB).filter(AuditLogDB.id == log_id).first()
    if not db_log:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audit log not found"
        )
    
    # 转换为响应模型
    from ..services.audit_service import AuditService
    audit_service = AuditService()
    return audit_service._to_response(db_log)


@router.get("/metrics")
async def get_metrics(
    db: Session = Depends(get_db),
    token: str = Depends(verify_admin_token)
):
    """
    获取实时统计指标
    """
    from ..models.api_key import APIKeyDB
    from ..models.proxy_route import ProxyRouteDB
    from ..models.audit_log import AuditLogDB
    from sqlalchemy import func
    
    # 获取基础统计
    total_keys = db.query(APIKeyDB).count()
    active_keys = db.query(APIKeyDB).filter(APIKeyDB.is_active == True).count()
    total_routes = db.query(ProxyRouteDB).count()
    active_routes = db.query(ProxyRouteDB).filter(ProxyRouteDB.is_active == True).count()
    
    # 获取请求统计
    total_requests = db.query(AuditLogDB).count()
    total_errors = db.query(AuditLogDB).filter(AuditLogDB.status_code >= 400).count()
    
    # 计算成功率
    success_rate = ((total_requests - total_errors) / total_requests * 100) if total_requests > 0 else 100.0
    
    # 计算平均响应时间
    avg_response_time = db.query(func.avg(AuditLogDB.response_time_ms)).scalar() or 0
    
    # 获取TOP路径
    top_paths = db.query(
        AuditLogDB.path,
        func.count(AuditLogDB.path).label('count')
    ).group_by(AuditLogDB.path).order_by(func.count(AuditLogDB.path).desc()).limit(5).all()
    
    # 获取TOP来源
    top_source_paths = db.query(
        AuditLogDB.source_path,
        func.count(AuditLogDB.source_path).label('count')
    ).group_by(AuditLogDB.source_path).order_by(func.count(AuditLogDB.source_path).desc()).limit(5).all()
    
    # 获取TOP API Key 调用者
    top_api_keys = db.query(
        APIKeyDB.source_path,
        func.count(AuditLogDB.id).label('count')
    ).join(APIKeyDB, AuditLogDB.api_key == APIKeyDB.key_value)\
     .group_by(APIKeyDB.source_path)\
     .order_by(func.count(AuditLogDB.id).desc())\
     .limit(5).all()

    # 状态码分布
    status_distribution = {}
    status_stats = db.query(
        AuditLogDB.status_code,
        func.count(AuditLogDB.status_code).label('count')
    ).group_by(AuditLogDB.status_code).all()
    
    for status_code, count in status_stats:
        status_distribution[str(status_code)] = count
    
    return {
        "total_requests": total_requests,
        "total_errors": total_errors,
        "success_rate": round(success_rate, 2),
        "average_response_time": round(avg_response_time, 2) if avg_response_time else 0,
        "p95_response_time": 0,  # TODO: 实现P95计算
        "requests_per_minute": 0,  # TODO: 实现每分钟请求数
        "active_api_keys": active_keys,
        "active_routes": active_routes,
        "top_paths": [{"path": path, "count": count} for path, count in top_paths],
        "top_source_paths": [{"source_path": source_path, "count": count} for source_path, count in top_source_paths],
        "top_api_keys": [{"source_path": path, "count": count} for path, count in top_api_keys],
        "status_distribution": status_distribution
    }


@router.get("/metrics/hourly")
async def get_hourly_metrics(
    hours: int = Query(24, ge=1, le=168, description="获取最近多少小时的数据"),
    db: Session = Depends(get_db),
    token: str = Depends(verify_admin_token)
):
    """
    获取按小时统计的指标数据
    """
    from ..models.audit_log import AuditLogDB, china_tz
    from sqlalchemy import func, and_
    from datetime import datetime, timedelta
    
    # 计算时间范围 - 使用中国时区
    end_time = datetime.now(china_tz)
    start_time = end_time - timedelta(hours=hours)
    
    # 转换为数据库存储格式（中国时区的本地时间）
    start_time_local = start_time.replace(tzinfo=None)
    end_time_local = end_time.replace(tzinfo=None)
    
    # 按小时分组查询 - 使用 SQLite 兼容的 strftime 函数
    hourly_stats = db.query(
        func.strftime('%Y-%m-%d %H:00:00', AuditLogDB.request_time).label('hour'),
        func.count(AuditLogDB.id).label('total_requests'),
        func.count().filter(AuditLogDB.status_code >= 400).label('errors'),
        func.avg(AuditLogDB.response_time_ms).label('avg_response_time')
    ).filter(
        and_(
            AuditLogDB.request_time >= start_time_local,
            AuditLogDB.request_time <= end_time_local
        )
    ).group_by(
        func.strftime('%Y-%m-%d %H:00:00', AuditLogDB.request_time)
    ).order_by('hour').all()
    
    return [
        {
            "hour": stat.hour,  # strftime 已经返回字符串格式，不需要 isoformat()
            "total_requests": stat.total_requests,
            "errors": stat.errors or 0,
            "success_rate": round(((stat.total_requests - (stat.errors or 0)) / stat.total_requests * 100), 2) if stat.total_requests > 0 else 100.0,
            "avg_response_time": round(stat.avg_response_time, 2) if stat.avg_response_time else 0
        }
        for stat in hourly_stats
    ]


@router.get("/metrics/daily")
async def get_daily_metrics(
    days: int = Query(30, ge=1, le=365, description="获取最近多少天的数据"),
    db: Session = Depends(get_db),
    token: str = Depends(verify_admin_token)
):
    """
    获取按天统计的指标数据
    """
    from ..models.audit_log import AuditLogDB, china_tz
    from sqlalchemy import func, and_
    from datetime import datetime, timedelta
    
    # 计算时间范围 - 使用中国时区
    end_time = datetime.now(china_tz)
    start_time = end_time - timedelta(days=days)
    
    # 转换为数据库存储格式（中国时区的本地时间）
    start_time_local = start_time.replace(tzinfo=None)
    end_time_local = end_time.replace(tzinfo=None)
    
    # 按天分组查询 - 使用 SQLite 兼容的 strftime 函数
    daily_stats = db.query(
        func.strftime('%Y-%m-%d', AuditLogDB.request_time).label('day'),
        func.count(AuditLogDB.id).label('total_requests'),
        func.count().filter(AuditLogDB.status_code >= 400).label('errors'),
        func.avg(AuditLogDB.response_time_ms).label('avg_response_time')
    ).filter(
        and_(
            AuditLogDB.request_time >= start_time_local,
            AuditLogDB.request_time <= end_time_local
        )
    ).group_by(
        func.strftime('%Y-%m-%d', AuditLogDB.request_time)
    ).order_by('day').all()
    
    return [
        {
            "day": stat.day,  # strftime 已经返回字符串格式，不需要 isoformat()
            "total_requests": stat.total_requests,
            "errors": stat.errors or 0,
            "success_rate": round(((stat.total_requests - (stat.errors or 0)) / stat.total_requests * 100), 2) if stat.total_requests > 0 else 100.0,
            "avg_response_time": round(stat.avg_response_time, 2) if stat.avg_response_time else 0
        }
        for stat in daily_stats
    ]

 