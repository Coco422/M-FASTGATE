# API 设计文档 - v0.2.2

## API概述

M-FastGate是一个基于FastAPI的轻量级网关系统，提供以下主要功能：
- API Key管理
- 通用反向代理转发
- HTTP请求审计日志
- 流式响应支持
- Web管理界面

**基础URL**: `http://host:port`  
**认证方式**: API Key认证 + Admin Token认证  
**数据格式**: JSON  

## 认证机制

### 1. API Key认证
用于业务API调用，在请求头中携带：
```
Authorization: Bearer {api_key}
```
或
```
X-API-Key: {api_key}
```

### 2. Admin Token认证
用于管理接口调用，在请求头中携带：
```
Authorization: Bearer {admin_token}
```

## API 端点分类

### 一、健康检查接口

#### GET /health
**描述**: 系统健康检查  
**认证**: 无需认证  
**响应示例**:
```json
{
    "status": "healthy",
    "timestamp": "2024-01-01T12:00:00.000Z",
    "version": "0.2.0",
    "name": "M-FastGate",
    "gateway": {
        "backend_url": "http://172.16.99.32:1030",
        "backend_path": "/miniai/v2/chat/completions",
        "async_audit": true
    }
}
```

#### GET /
**描述**: 根路径信息  
**认证**: 无需认证  
**响应示例**:
```json
{
    "name": "M-FastGate",
    "version": "0.2.0",
    "description": "M-FastGate 网关系统",
    "docs_url": "/docs",
    "health_url": "/health",
    "admin_prefix": "/admin",
    "web_ui_url": "/admin/ui",
    "proxy_endpoints": {
        "universal_proxy": "/{path:path}",
        "route_management": "/admin/routes"
    }
}
```

### 二、管理接口 (/admin)

#### API Key管理

##### POST /admin/keys
**描述**: 创建新的API Key  
**认证**: Admin Token  
**请求体**:
```json
{
    "source_path": "string",           // 必需，来源路径标识
    "permissions": ["string"],         // 可选，权限列表，默认为[]
    "expires_days": 30,                // 可选，有效天数
    "rate_limit": 1000                 // 可选，速率限制
}
```
**响应示例**:
```json
{
    "key_id": "fg_abc123def456",
    "key_value": "fg_xyz789abc123def456ghi789jkl012mno345pqr678stu901",
    "source_path": "test_app",
    "permissions": [],
    "created_at": "2024-01-01T12:00:00.000Z",
    "expires_at": "2024-01-31T12:00:00.000Z",
    "is_active": true,
    "usage_count": 0,
    "rate_limit": 1000,
    "last_used_at": null
}
```

##### GET /admin/keys
**描述**: 获取API Key列表  
**认证**: Admin Token  
**查询参数**:
- `skip`: int = 0 - 跳过的记录数
- `limit`: int = 100 - 返回的记录数
- `source_path`: str = None - 按来源路径过滤
- `is_active`: bool = None - 按活跃状态过滤

**响应示例**:
```json
[
    {
        "key_id": "fg_abc123def456",
        "key_value": "fg_xyz789abc123def456ghi789jkl012mno345pqr678stu901",
        "source_path": "test_app",
        "permissions": [],
        "created_at": "2024-01-01T12:00:00.000Z",
        "expires_at": "2024-01-31T12:00:00.000Z",
        "is_active": true,
        "usage_count": 5,
        "rate_limit": 1000,
        "last_used_at": "2024-01-01T14:30:00.000Z"
    }
]
```

##### GET /admin/keys/{key_id}
**描述**: 获取API Key详情  
**认证**: Admin Token  
**路径参数**:
- `key_id`: str - API Key ID

**响应**: 同POST /admin/keys响应格式

##### PUT /admin/keys/{key_id}
**描述**: 更新API Key  
**认证**: Admin Token  
**路径参数**:
- `key_id`: str - API Key ID

**请求体**:
```json
{
    "source_path": "string",           // 可选
    "permissions": ["string"],         // 可选
    "expires_at": "2024-01-31T12:00:00.000Z", // 可选
    "is_active": true,                 // 可选
    "rate_limit": 2000                 // 可选
}
```

##### DELETE /admin/keys/{key_id}
**描述**: 删除API Key  
**认证**: Admin Token  
**路径参数**:
- `key_id`: str - API Key ID

**响应示例**:
```json
{
    "message": "API Key deleted successfully"
}
```

#### 代理路由配置管理

##### POST /admin/routes
**描述**: 创建新的代理路由配置  
**认证**: Admin Token  
**请求体**:
```json
{
    "route_name": "string",            // 必需，路由名称
    "description": "string",           // 可选，路由描述
    "match_path": "/v1/*",             // 必需，匹配路径模式
    "match_method": "POST",            // 可选，匹配HTTP方法，默认ANY
    "match_headers": {},               // 可选，匹配请求头条件
    "match_body_schema": {},           // 可选，匹配请求体结构
    "target_host": "172.16.99.204:3398", // 必需，目标主机
    "target_path": "/v1/chat/completions", // 必需，目标路径
    "target_protocol": "http",         // 可选，协议，默认http
    "strip_path_prefix": false,        // 可选，是否剔除路径前缀
    "add_headers": {},                 // 可选，新增请求头
    "add_body_fields": {},             // 可选，新增请求体字段
    "remove_headers": [],              // 可选，移除请求头列表
    "timeout": 30,                     // 可选，超时时间（秒）
    "retry_count": 0,                  // 可选，重试次数
    "priority": 100,                   // 可选，优先级
    "is_active": true                  // 可选，是否启用
}
```

**响应示例**:
```json
{
    "route_id": "route_abc123def456",
    "route_name": "OpenAI Chat API",
    "description": "代理OpenAI聊天接口",
    "match_path": "/v1/chat/completions",
    "match_method": "POST",
    "target_host": "172.16.99.204:3398",
    "target_path": "/v1/chat/completions",
    "target_protocol": "http",
    "is_active": true,
    "priority": 10,
    "created_at": "2024-01-01T12:00:00.000Z",
    "updated_at": "2024-01-01T12:00:00.000Z"
}
```

##### GET /admin/routes
**描述**: 获取所有代理路由配置  
**认证**: Admin Token  
**查询参数**:
- `skip`: int = 0 - 跳过的记录数
- `limit`: int = 100 - 返回的记录数
- `is_active`: bool = None - 按活跃状态过滤

##### GET /admin/routes/{route_id}
**描述**: 获取单个代理路由配置详情  
**认证**: Admin Token  
**路径参数**:
- `route_id`: str - 路由ID

##### PUT /admin/routes/{route_id}
**描述**: 更新代理路由配置  
**认证**: Admin Token  
**路径参数**:
- `route_id`: str - 路由ID
**请求体**: 同POST /admin/routes，所有字段可选

##### DELETE /admin/routes/{route_id}
**描述**: 删除代理路由配置  
**认证**: Admin Token  
**路径参数**:
- `route_id`: str - 路由ID

**响应示例**:
```json
{
    "message": "Route deleted successfully"
}
```

##### POST /admin/routes/{route_id}/toggle
**描述**: 切换路由状态  
**认证**: Admin Token  
**路径参数**:
- `route_id`: str - 路由ID
**请求体**:
```json
{
    "is_active": true
}
```

#### 审计日志查询

##### GET /admin/logs
**描述**: 获取审计日志  
**认证**: Admin Token  
**查询参数**:
- `skip`: int = 0 - 跳过的记录数
- `limit`: int = 50 - 返回的记录数
- `api_key`: str = None - 按API Key过滤
- `source_path`: str = None - 按来源路径过滤
- `method`: str = None - 按请求方法过滤
- `status_code`: int = None - 按状态码过滤

**响应示例**:
```json
[
    {
        "id": "log_abc123def456",
        "request_id": "req_xyz789abc123",
        "api_key": "fg_xyz789abc123def456ghi789jkl012mno345pqr678stu901",
        "source_path": "test_app",
        "method": "POST",
        "path": "/v1/chat/completions",
        "target_url": "http://172.16.99.204:3398/v1/chat/completions",
        "status_code": 200,
        "request_time": "2024-01-01T12:00:00.000Z",
        "first_response_time": "2024-01-01T12:00:00.100Z",
        "response_time": "2024-01-01T12:00:01.500Z",
        "response_time_ms": 1500,
        "request_size": 256,
        "response_size": 1024,
        "user_agent": "curl/7.68.0",
        "ip_address": "192.168.1.100",
        "error_message": null,
        "is_stream": false,
        "stream_chunks": 0,
        "request_headers": "{\"Content-Type\":\"application/json\",\"Authorization\":\"Bearer fg_...\"}",
        "request_body": "{\"model\":\"gpt-3.5-turbo\",\"messages\":[...]}",
        "response_headers": "{\"Content-Type\":\"application/json\"}",
        "response_body": "{\"choices\":[...]}",
        "created_at": "2024-01-01T12:00:00.000Z"
    }
]
```

#### 统计指标

##### GET /admin/metrics
**描述**: 获取统计指标  
**认证**: Admin Token  
**响应示例**:
```json
{
    "total_requests": 1000,
    "total_errors": 10,
    "average_response_time": 850.5,
    "requests_per_hour": 42,
    "active_api_keys": 5,
    "top_source_paths": [
        {"source_path": "app1", "count": 500},
        {"source_path": "app2", "count": 300}
    ]
}
```

##### GET /admin/metrics/hourly
**描述**: 获取按小时统计的指标数据  
**认证**: Admin Token  
**查询参数**:
- `hours`: int = 24 - 获取最近多少小时的数据

##### GET /admin/metrics/trends
**描述**: 获取趋势数据  
**认证**: Admin Token  
**查询参数**:
- `days`: int = 30 - 获取最近多少天的数据
- `group_by`: str = "day" - 分组方式（day|hour）



### 三、Web管理界面 (/admin/ui)

#### GET /admin/ui/
**描述**: 管理面板首页  
**认证**: Admin Token  
**响应**: HTML页面

#### GET /admin/ui/keys
**描述**: API Key管理页面  
**认证**: Admin Token  
**响应**: HTML页面

#### GET /admin/ui/logs
**描述**: 审计日志页面  
**认证**: Admin Token  
**响应**: HTML页面

#### GET /admin/ui/static/{file_path}
**描述**: 静态文件服务  
**认证**: 无需认证

### 四、通用代理接口

#### ANY /{path:path}
**描述**: 通用代理转发接口，根据路由配置将请求转发到目标服务器  
**认证**: API Key  
**支持方法**: GET, POST, PUT, DELETE, PATCH, HEAD, OPTIONS  

**工作流程**:
1. 验证API Key
2. 根据路径、方法、请求头等条件匹配路由配置（按优先级排序）
3. 应用路由转换规则（添加/删除请求头、修改请求体等）
4. 异步记录审计日志开始
5. 转发请求到目标服务器
6. 处理响应（支持流式响应）
7. 更新审计日志完成记录
8. 返回响应给客户端

**路径匹配示例**:
- 请求: `POST /v1/chat/completions` -> 匹配路由: `match_path="/v1/*"`
- 请求: `GET /api/v2/users/123` -> 匹配路由: `match_path="/api/v2/*"`

**流式响应处理**:
系统会自动检测流式响应（基于Content-Type和请求体stream字段），并正确处理Server-Sent Events格式的响应流。

**请求体示例** (OpenAI风格):
```json
{
    "model": "gpt-3.5-turbo",
    "messages": [
        {"role": "user", "content": "Hello"}
    ],
    "stream": true,
    "temperature": 0.7
}
```

**响应处理**:
- 非流式响应: 直接返回完整JSON响应
- 流式响应: 返回Server-Sent Events流，保持连接直到流结束

## 错误响应格式

### 标准错误响应
```json
{
    "detail": "错误信息描述"
}
```

### 常见错误状态码
- `400 Bad Request`: 请求参数错误
- `401 Unauthorized`: 认证失败
- `403 Forbidden`: 权限不足
- `404 Not Found`: 资源不存在
- `422 Unprocessable Entity`: 请求参数验证失败
- `429 Too Many Requests`: 请求过于频繁
- `500 Internal Server Error`: 服务器内部错误
- `502 Bad Gateway`: 上游服务连接失败
- `503 Service Unavailable`: 服务不可用
- `504 Gateway Timeout`: 上游服务超时

## 配置信息

### 默认配置
- **服务端口**: 8514
- **数据库**: SQLite (app/data/fastgate.db)
- **配置文件**: config.yaml
- **默认超时**: 30秒
- **日志级别**: INFO
- **认证前缀**: fg_
- **异步审计**: 启用

### 环境变量
- `FASTGATE_ADMIN_TOKEN`: 管理员令牌（必需）
- `FASTGATE_CONFIG`: 配置文件路径（可选，默认config.yaml）
- `FASTGATE_ENV`: 运行环境（可选，development/production） 