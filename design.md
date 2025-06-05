# M-FastGate 网关设计文档

## 项目概述

M-FastGate 是一个基于 FastAPI 的轻量级网关系统，主要提供以下核心功能：
- API Key 分发与管理
- 多路径路由聚合
- 请求审计与日志记录
- 统一渠道配置管理

## 架构设计

### 整体架构

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Client Apps   │───▶│   M-FastGate    │───▶│  Target APIs    │
│                 │    │   (Gateway)     │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                              │
                              ▼
                       ┌─────────────────┐
                       │   Audit Logs    │
                       │   & Metrics     │
                       └─────────────────┘
```

### 技术栈

- **Web框架**: FastAPI
- **数据库**: SQLite (开发) / PostgreSQL (生产)
- **缓存**: Redis (可选)
- **配置管理**: Pydantic Settings
- **日志**: structlog
- **监控**: Prometheus metrics (可选)

## 核心功能模块

### 1. API Key 管理模块

**功能职责:**
- API Key 生成与分发
- Key 权限管理
- Key 使用统计
- 来源路径标记

**数据模型:**
```python
class APIKey(BaseModel):
    key_id: str
    key_value: str
    source_path: str  # 来源标识
    permissions: List[str]  # 权限列表
    created_at: datetime
    expires_at: Optional[datetime]
    is_active: bool
    usage_count: int
    rate_limit: Optional[int]
```

### 2. 路由聚合模块

**功能职责:**
- 多路径路由配置
- 请求分发逻辑
- 负载均衡
- 失败重试

**路由配置示例:**
```yaml
routes:
  - path: "/api/v1/users"
    methods: ["GET", "POST"]
    targets:
      - url: "http://user-service:8001"
        weight: 70
      - url: "http://user-service-backup:8001"
        weight: 30
    timeout: 30
    retry_count: 3
```

### 3. 审计日志模块

**功能职责:**
- 请求/响应日志记录
- 性能指标统计
- 错误追踪
- 访问审计

**日志格式:**
```json
{
  "timestamp": "2024-01-15T10:30:00Z",
  "request_id": "req_12345",
  "api_key": "key_abc123",
  "source_path": "mobile_app",
  "method": "GET",
  "path": "/api/v1/users",
  "target_url": "http://user-service:8001/users",
  "status_code": 200,
  "response_time_ms": 150,
  "request_size": 256,
  "response_size": 1024,
  "user_agent": "MyApp/1.0",
  "ip_address": "192.168.1.100"
}
```

### 4. 渠道配置模块

**功能职责:**
- 统一配置管理
- 动态配置更新
- 配置验证
- 环境隔离

## API 设计

### 管理接口

```python
# API Key 管理
POST /admin/keys              # 创建 API Key
GET  /admin/keys              # 列出所有 Key
GET  /admin/keys/{key_id}     # 获取 Key 详情
PUT  /admin/keys/{key_id}     # 更新 Key
DELETE /admin/keys/{key_id}   # 删除 Key

# 路由配置管理
GET  /admin/routes            # 获取路由配置
POST /admin/routes            # 创建/更新路由
DELETE /admin/routes/{route_id} # 删除路由

# 审计日志查询
GET  /admin/logs              # 查询日志
GET  /admin/metrics           # 获取统计指标
```

### 网关代理接口

```python
# 通用代理接口 (支持所有 HTTP 方法)
ANY /{path:path}              # 代理转发请求
```

### 认证与鉴权

**Header 认证:**
```
X-API-Key: your_api_key_here
X-Source-Path: mobile_app
```

## 项目结构

```
M-FastGate/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI 应用入口
│   ├── config.py              # 配置管理
│   ├── database.py            # 数据库连接
│   ├── models/                # 数据模型
│   │   ├── __init__.py
│   │   ├── api_key.py
│   │   ├── route.py
│   │   └── audit_log.py
│   ├── api/                   # API 路由
│   │   ├── __init__.py
│   │   ├── admin.py          # 管理接口
│   │   └── proxy.py          # 代理接口
│   ├── services/              # 业务逻辑
│   │   ├── __init__.py
│   │   ├── key_manager.py
│   │   ├── route_manager.py
│   │   └── audit_service.py
│   ├── middleware/            # 中间件
│   │   ├── __init__.py
│   │   ├── auth.py
│   │   └── logging.py
│   └── utils/                 # 工具函数
│       ├── __init__.py
│       └── helpers.py
├── config/                    # 配置文件
│   ├── development.yaml
│   ├── production.yaml
│   └── routes.yaml
├── logs/                      # 日志文件目录
├── tests/                     # 测试文件
├── docker-compose.yml         # Docker 编排
├── Dockerfile                 # Docker 镜像
├── requirements.txt           # Python 依赖
├── alembic.ini               # 数据库迁移配置
└── README.md                 # 项目说明
```

## 核心流程

### 1. 请求处理流程

```
1. 客户端请求 → 2. 认证中间件 → 3. 日志中间件 → 4. 路由匹配 
                     ↓              ↓              ↓
5. 目标服务调用 ← 6. 响应处理 ← 7. 审计记录 ← 8. 错误处理
```

### 2. Key 管理流程

```
1. 管理员创建 Key → 2. 生成唯一标识 → 3. 设置权限 → 4. 存储数据库
                                        ↓
5. 客户端使用 Key → 6. 验证有效性 → 7. 记录使用 → 8. 更新统计
```

## 配置示例

### 应用配置 (config/development.yaml)

```yaml
app:
  name: "M-FastGate"
  version: "0.0.1"
  debug: true
  host: "0.0.0.0"
  port: 8000

database:
  url: "sqlite:///./fastgate.db"
  echo: true

logging:
  level: "INFO"
  format: "json"
  file: "logs/fastgate.log"

security:
  admin_token: "admin_secret_token"
  key_prefix: "fg_"
  default_expiry_days: 365

rate_limiting:
  enabled: true
  default_requests_per_minute: 100
```

### 路由配置 (config/routes.yaml)

```yaml
routes:
  - name: "用户服务"
    path_prefix: "/api/v1/users"
    targets:
      - url: "http://localhost:8001"
        timeout: 30
    auth_required: true
    
  - name: "订单服务"
    path_prefix: "/api/v1/orders"
    targets:
      - url: "http://localhost:8002"
        timeout: 45
    auth_required: true
    rate_limit: 200
```

## 部署方案

### Docker 部署

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Docker Compose

```yaml
version: '3.8'
services:
  fastgate:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://user:pass@db:5432/fastgate
    depends_on:
      - db
      
  db:
    image: postgres:13
    environment:
      - POSTGRES_DB=fastgate
      - POSTGRES_USER=user
      - POSTGRES_PASSWORD=pass
    volumes:
      - postgres_data:/var/lib/postgresql/data

volumes:
  postgres_data:
```

## 监控与运维

### 健康检查

```python
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow(),
        "version": app.version
    }
```

### 指标监控

- 请求总数
- 响应时间分布
- 错误率
- API Key 使用统计
- 目标服务健康状态

## 安全考虑

1. **API Key 安全**: 
   - 定期轮换
   - 权限最小化原则
   - 传输加密

2. **请求验证**:
   - 输入参数校验
   - SQL 注入防护
   - XSS 防护

3. **访问控制**:
   - IP 白名单
   - 频率限制
   - 熔断机制

## 扩展性考虑

1. **水平扩展**: 支持多实例部署
2. **缓存优化**: Redis 缓存热点数据
3. **异步处理**: 日志异步写入
4. **插件机制**: 支持自定义中间件

## 开发计划

### Phase 1: 核心功能
- [ ] FastAPI 基础框架
- [ ] API Key 管理
- [ ] 基础路由代理
- [ ] 简单日志记录

### Phase 2: 增强功能
- [ ] 路由配置管理
- [ ] 详细审计日志
- [ ] 性能监控
- [ ] 管理界面

### Phase 3: 生产优化
- [ ] 高可用部署
- [ ] 性能优化
- [ ] 安全加固
- [ ] 文档完善 