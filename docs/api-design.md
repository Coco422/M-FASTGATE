# API 设计文档 - v0.2.3

## API概述

M-FastGate v0.2.0是一个基于FastAPI的统一API网关系统，提供以下核心功能：
- 统一反向代理网关（nginx级别代理能力）
- 智能路由匹配和转发
- API Key安全隔离管理
- 完整的HTTP请求审计日志
- 流式响应完整支持
- Web管理界面和路由配置

**基础URL**: `http://host:port`  
**默认端口**: 8514
**认证方式**: API Key认证 + Admin Token认证  
**数据格式**: JSON  
**当前版本**: v0.2.0

## 认证机制

### 1. API Key认证（网关用户）
用于通过网关访问后端服务，网关自动处理密钥转换：
```
Authorization: Bearer {gateway_api_key}
```

**工作流程**:
- 用户使用网关分配的API密钥
- 网关验证用户密钥有效性
- 网关自动转换为后端服务密钥
- 用户无需知道真实后端API密钥

### 2. Admin Token认证（管理员）
用于管理接口调用：
```
Authorization: Bearer {admin_token}
```

## API 端点分类

### 一、系统健康检查接口

#### GET /health
**描述**: 系统健康检查  
**认证**: 无需认证  
**响应示例**:
```json
{
    "status": "healthy",
    "timestamp": "2024-06-06T04:00:00.000Z",
    "version": "0.2.0",
    "name": "M-FastGate",
    "gateway": {
        "total_routes": 2,
        "active_routes": 2,
        "active_api_keys": 3,
        "proxy_engine": "initialized"
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
    "description": "统一API网关系统 - nginx级别反向代理",
    "docs_url": "/docs",
    "health_url": "/health",
    "admin_prefix": "/admin",
    "web_ui_url": "/admin/ui",
    "proxy_endpoints": {
        "universal_proxy": "/{path:path}",
        "supported_methods": ["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"]
    },
    "features": [
        "统一反向代理",
        "智能路由匹配",
        "API密钥隔离",
        "流式响应支持",
        "完整审计日志"
    ]
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
    "source_path": "string",           // 必需，来源标识
    "permissions": ["string"],         // 可选，权限列表，默认为[]
    "expires_days": 365,               // 可选，有效天数，默认365
    "rate_limit": 1000                 // 可选，速率限制
}
```
**响应示例**:
```json
{
    "key_id": "fg_bb86925dc378",
    "key_value": "fg__XINmxeEYjcyfnl-GYpqTQkdcrTixijQ82hDUSbdmKI",
    "source_path": "qwen3-30b-gateway",
    "permissions": ["chat.completions", "models.list"],
    "created_at": "2024-06-06T04:00:00.000Z",
    "expires_at": "2025-06-06T04:00:00.000Z",
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
        "key_id": "fg_bb86925dc378",
        "key_value": "fg__XINmxeEYjcyfnl-GYpqTQkdcrTixijQ82hDUSbdmKI",
        "source_path": "qwen3-30b-gateway",
        "permissions": ["chat.completions", "models.list"],
        "created_at": "2024-06-06T04:00:00.000Z",
        "expires_at": "2025-06-06T04:00:00.000Z",
        "is_active": true,
        "usage_count": 5,
        "rate_limit": 1000,
        "last_used_at": "2024-06-06T04:30:00.000Z"
    }
]
```

##### GET /admin/keys/{key_id}
**描述**: 获取API Key详情  
**认证**: Admin Token  
**路径参数**:
- `key_id`: str - API Key ID

##### PUT /admin/keys/{key_id}
**描述**: 更新API Key  
**认证**: Admin Token  
**请求体**:
```json
{
    "source_path": "string",           // 可选
    "permissions": ["string"],         // 可选
    "expires_at": "2025-06-06T04:00:00.000Z", // 可选
    "is_active": true,                 // 可选
    "rate_limit": 2000                 // 可选
}
```

##### DELETE /admin/keys/{key_id}
**描述**: 删除API Key  
**认证**: Admin Token  

#### 代理路由配置管理

##### POST /admin/routes
**描述**: 创建新的代理路由配置  
**认证**: Admin Token  
**请求体**:
```json
{
    "route_name": "string",            // 必需，路由名称
    "description": "string",           // 可选，路由描述
    "match_path": "/v1/*",             // 必需，匹配路径模式（支持正则）
    "match_method": "POST",            // 可选，匹配HTTP方法，默认ANY
    "match_headers": "{}",             // 可选，匹配请求头条件（JSON字符串）
    "match_body_schema": "{}",         // 可选，匹配请求体结构（JSON字符串）
    "target_host": "172.16.99.204:3398", // 必需，目标主机:端口
    "target_path": "/v1/chat/completions", // 必需，目标路径
    "target_protocol": "http",         // 可选，协议，默认http
    "strip_path_prefix": false,        // 可选，是否剔除路径前缀
    "add_headers": "{\"Authorization\": \"Bearer sk-xxx\", \"X-Proxy-Source\": \"M-FastGate-v0.2.0\"}", // 可选，新增请求头（JSON字符串）
    "add_body_fields": "{}",           // 可选，新增请求体字段（JSON字符串）
    "remove_headers": "[\"host\"]",    // 可选，移除请求头列表（JSON字符串）
    "timeout": 30,                     // 可选，超时时间（秒）
    "retry_count": 0,                  // 可选，重试次数
    "priority": 100,                   // 可选，优先级（数字越小优先级越高）
    "is_active": true                  // 可选，是否启用
}
```

**响应示例**:
```json
{
    "route_id": "qwen3-30b-chat",
    "route_name": "Qwen3-30B Chat Completions",
    "description": "Qwen3-30B模型聊天完成接口 - 172.16.99.204:3398",
    "match_path": "/v1/chat/completions",
    "match_method": "POST",
    "match_body_schema": "{\"model\": \"mckj/Qwen3-30B-A3B\"}",
    "target_host": "172.16.99.204:3398",
    "target_path": "/v1/chat/completions",
    "target_protocol": "http",
    "strip_path_prefix": false,
    "add_headers": "{\"Authorization\": \"Bearer sk-nsItInRUqh7KFKX8l3xVOvLVaRJQo1iNi6ALl6rBUjqTdgFc\", \"X-Proxy-Source\": \"M-FastGate-v0.2.0\"}",
    "add_body_fields": "{\"source\": \"fastgate\"}",
    "remove_headers": "[\"host\"]",
    "is_active": true,
    "priority": 100,
    "created_at": "2024-06-06T04:00:00.000Z",
    "updated_at": "2024-06-06T04:00:00.000Z"
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

##### PUT /admin/routes/{route_id}
**描述**: 更新代理路由配置  
**认证**: Admin Token  
**请求体**: 同POST /admin/routes，所有字段可选

##### DELETE /admin/routes/{route_id}
**描述**: 删除代理路由配置  
**认证**: Admin Token  

##### POST /admin/routes/{route_id}/toggle
**描述**: 切换路由启用/禁用状态  
**认证**: Admin Token  
**请求体**:
```json
{
    "is_active": true
}
```

##### POST /admin/routes/{route_id}/test
**描述**: 测试代理路由配置（新增）  
**认证**: Admin Token  
**请求体**:
```json
{
    "test_method": "POST",             // 测试HTTP方法
    "test_headers": {},                // 测试请求头
    "test_body": {},                   // 测试请求体
    "timeout": 10                      // 测试超时时间
}
```
**响应示例**:
```json
{
    "success": true,
    "matched": true,
    "target_url": "http://172.16.99.204:3398/v1/chat/completions",
    "response_time_ms": 150,
    "status_code": 200,
    "error_message": null,
    "test_result": {
        "request_sent": true,
        "response_received": true,
        "headers_applied": true,
        "body_modified": true
    }
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
- `path`: str = None - 按请求路径过滤
- `status_code`: int = None - 按状态码过滤
- `start_time`: str = None - 开始时间过滤（ISO格式）
- `end_time`: str = None - 结束时间过滤（ISO格式）
- `is_stream`: bool = None - 按流式响应过滤

**响应示例**:
```json
[
    {
        "id": "log_35c3150a3db1",
        "request_id": "req_75bff36361b0",
        "api_key": "fg__XINmxeEYjcyfnl-GYpqTQkdcrTixijQ82hDUSbdmKI",
        "source_path": "qwen3-30b-gateway",
        "method": "POST",
        "path": "/v1/chat/completions",
        "target_url": "http://172.16.99.204:3398/v1/chat/completions",
        "status_code": 200,
        "request_time": "2024-06-06T04:08:56.000Z",
        "first_response_time": "2024-06-06T04:08:56.100Z",
        "response_time": "2024-06-06T04:08:56.037Z",
        "response_time_ms": 37,
        "request_size": 256,
        "response_size": 1024,
        "user_agent": "curl/7.68.0",
        "ip_address": "127.0.0.1",
        "error_message": null,
        "is_stream": false,
        "stream_chunks": 0,
        "created_at": "2024-06-06T04:08:56.000Z"
    }
]
```

##### GET /admin/logs/export
**描述**: 导出审计日志（新增）  
**认证**: Admin Token  
**查询参数**: 同GET /admin/logs，额外参数：
- `format`: str = "csv" - 导出格式（csv|json|xlsx）
- `include_headers`: bool = false - 是否包含请求/响应头
- `include_body`: bool = false - 是否包含请求/响应体

**响应**: 文件下载（CSV/JSON/Excel格式）

##### GET /admin/logs/{log_id}
**描述**: 获取单条审计日志详情  
**认证**: Admin Token  

#### 统计指标和仪表板

##### GET /admin/metrics
**描述**: 获取实时统计指标  
**认证**: Admin Token  
**响应示例**:
```json
{
    "total_requests": 1000,
    "total_errors": 10,
    "success_rate": 99.0,
    "average_response_time": 150.5,
    "p95_response_time": 300.0,
    "requests_per_minute": 42,
    "active_api_keys": 3,
    "active_routes": 2,
    "top_paths": [
        {"path": "/v1/chat/completions", "count": 500},
        {"path": "/v1/models", "count": 200}
    ],
    "top_source_paths": [
        {"source_path": "qwen3-30b-gateway", "count": 500},
        {"source_path": "test-app", "count": 300}
    ],
    "status_distribution": {
        "200": 950,
        "400": 5,
        "500": 5
    }
}
```

##### GET /admin/metrics/hourly
**描述**: 获取按小时统计的指标数据  
**认证**: Admin Token  
**查询参数**:
- `hours`: int = 24 - 获取最近多少小时的数据

##### GET /admin/metrics/daily
**描述**: 获取按天统计的指标数据（新增）  
**认证**: Admin Token  
**查询参数**:
- `days`: int = 30 - 获取最近多少天的数据

### 三、Web管理界面 (/admin/ui)

#### GET /admin/ui/
**描述**: 管理面板仪表板  
**认证**: Admin Token  
**响应**: HTML页面

#### GET /admin/ui/keys
**描述**: API Key管理页面  
**认证**: Admin Token  
**响应**: HTML页面

#### GET /admin/ui/routes
**描述**: 代理路由配置管理页面（新增）  
**认证**: Admin Token  
**响应**: HTML页面

#### GET /admin/ui/logs
**描述**: 审计日志查看页面  
**认证**: Admin Token  
**响应**: HTML页面

#### GET /admin/ui/static/{file_path}
**描述**: 静态文件服务  
**认证**: 无需认证

### 四、统一代理接口（核心功能）

#### ANY /{path:path}
**描述**: 统一代理转发接口 - M-FastGate v0.2.0的核心功能  
**认证**: API Key（网关密钥）  
**支持方法**: GET, POST, PUT, DELETE, PATCH, HEAD, OPTIONS  

**工作流程**:
1. 验证API Key（网关密钥验证）
2. 智能路由匹配（按优先级排序）
   - 路径模式匹配（支持正则表达式）
   - HTTP方法匹配
   - 请求体内容匹配（JSON Schema验证）
3. 应用路由转换规则
   - 添加/删除请求头（如API密钥转换）
   - 修改请求体字段
   - 路径前缀处理
4. 异步记录审计日志（请求开始）
5. 转发请求到目标服务器
   - 支持HTTP/HTTPS协议
   - 支持请求重试和超时控制
6. 处理响应
   - 自动检测流式响应
   - 支持SSE（Server-Sent Events）
   - 支持NDJSON格式
7. 更新审计日志（请求完成，包含TTFB时间）
8. 返回响应给客户端

**路径匹配示例**:
- 请求: `POST /v1/chat/completions` -> 匹配路由: `qwen3-30b-chat`
- 请求: `GET /v1/models` -> 匹配路由: `qwen3-30b-general`

**API密钥转换示例**:
```
用户请求头: Authorization: Bearer fg__XINmxeEYjcyfnl-GYpqTQkdcrTixijQ82hDUSbdmKI
↓ 网关自动转换
后端请求头: Authorization: Bearer sk-nsItInRUqh7KFKX8l3xVOvLVaRJQo1iNi6ALl6rBUjqTdgFc
```

**流式响应处理**:
系统自动检测流式响应（基于Content-Type和请求体stream字段），并正确处理Server-Sent Events格式的响应流。

**请求体示例** (OpenAI风格):
```json
{
    "model": "mckj/Qwen3-30B-A3B",
    "messages": [
        {"role": "user", "content": "Hello, how are you?"}
    ],
    "stream": true,
    "temperature": 0.7,
    "max_tokens": 100
}
```

## 错误响应格式

### 标准错误响应
```json
{
    "detail": "错误信息描述"
}
```

### 代理错误响应
```json
{
    "detail": "Internal proxy error",
    "error_type": "proxy_error",
    "request_id": "req_75bff36361b0"
}
```

### 路由匹配失败
```json
{
    "detail": "No matching route found",
    "path": "/v1/unknown/endpoint",
    "method": "POST"
}
```

### 常见错误状态码
- `400 Bad Request`: 请求参数错误
- `401 Unauthorized`: API Key认证失败
- `403 Forbidden`: 权限不足
- `404 Not Found`: 无匹配路由或资源不存在
- `422 Unprocessable Entity`: 请求参数验证失败
- `429 Too Many Requests`: 请求频率超限
- `500 Internal Server Error`: 网关内部错误
- `502 Bad Gateway`: 后端服务连接失败
- `503 Service Unavailable`: 服务不可用
- `504 Gateway Timeout`: 后端服务超时

## 配置信息

### 系统配置
- **服务端口**: 8514
- **数据库**: SQLite (./app/data/fastgate.db)
- **配置文件**: config/config.yaml（统一配置）
- **默认超时**: 300秒
- **日志级别**: INFO
- **API Key前缀**: fg_
- **异步审计**: 启用

### 环境变量支持
- `DATABASE_URL`: 数据库连接URL
- `ADMIN_TOKEN`: 管理员令牌
- `APP_PORT`: 应用端口
- `APP_HOST`: 应用主机地址

### v0.2.0新特性
- ✅ **统一代理网关**: nginx级别的反向代理能力
- ✅ **智能路由匹配**: 支持复杂的匹配规则和优先级
- ✅ **API密钥隔离**: 用户使用网关密钥，后端密钥完全隔离
- ✅ **完整流式支持**: 兼容OpenAI风格的流式API
- ✅ **三阶段审计**: 包含TTFB（首字节响应时间）
- ✅ **配置统一化**: 单一YAML配置文件
- ✅ **生产就绪**: 真实环境测试通过 