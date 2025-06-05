# M-FastGate 网关系统

一个基于 FastAPI 的轻量级API网关系统，提供 API Key 管理、统一端点代理、异步审计日志和Web管理界面等核心功能。

## 功能特性

- 🔑 **API Key 管理**: 支持 Key 的创建、更新、删除和验证
- 🌐 **API网关**: 统一端点多用户请求处理和后端转发
- 🛡️ **参数清洗**: 自动移除敏感信息，固定Key转发
- 📊 **异步审计**: 完整的请求追踪和统计分析（不阻塞业务）
- 🎨 **Web管理界面**: 现代化的实时监控和管理面板
- 🚀 **流式支持**: 完整支持OpenAI格式的SSE流式响应
- ⚙️ **配置管理**: YAML 配置文件和环境变量支持

## 环境要求

- Python 3.12+
- FastAPI 0.115.12+
- SQLAlchemy 2.0.41+

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置系统

编辑 `config/development.yaml` 配置API网关：

```yaml
api_gateway:
  backend_url: "http://172.16.99.32:1030"
  backend_path: "/miniai/v2/chat/completions"
  real_api_key: "your_real_api_key_here"  # 配置后端真实Key
  strip_headers:
    - "host"
    - "x-api-key"
    - "authorization"
  async_audit: true
```

### 3. 启动服务

```bash
# 开发模式（推荐端口8514）
python -m uvicorn app.main:app --host 0.0.0.0 --port 8514 --reload

# 或使用应用内置启动
python -m app.main
```

### 4. 访问服务

- **Web管理界面**: http://localhost:8514/admin/ui/?token=admin_secret_token_dev
- **API网关端点**: http://localhost:8514/proxy/miniai/v2/chat/completions
- **API 文档**: http://localhost:8514/docs
- **健康检查**: http://localhost:8514/health

## 核心功能使用

### API网关统一端点

所有用户使用同一个端点，系统自动转发：

```bash
# 用户1请求（流式）
curl -X POST "http://localhost:8514/proxy/miniai/v2/chat/completions" \
  -H "X-API-Key: user1_api_key" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-3.5-turbo",
    "messages": [{"role": "user", "content": "Hello"}],
    "stream": true
  }'

# 用户2请求（普通）
curl -X POST "http://localhost:8514/proxy/miniai/v2/chat/completions" \
  -H "X-API-Key: user2_api_key" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-3.5-turbo",
    "messages": [{"role": "user", "content": "Hi"}]
  }'
```

### Web管理界面功能

访问 `http://localhost:8514/admin/ui/?token=admin_secret_token_dev`

**主要功能**：
- 📊 **实时仪表板**: 统计卡片、请求趋势图、系统状态
- 🔑 **API Key管理**: 在线创建、查看、管理用户Key
- 📋 **审计日志**: 实时请求记录、流式/普通请求区分
- 🎯 **快速操作**: 一键创建Key、系统状态刷新
- 📱 **响应式设计**: 支持桌面和移动端访问

**界面特性**：
- 30秒自动刷新数据
- Chart.js图表展示趋势
- Bootstrap 5现代化设计
- 实时状态监控
- 加载状态管理

## API 使用指南

### 管理接口

所有管理接口都需要管理员令牌，通过 `token` 查询参数传递。

#### 创建 API Key

```bash
curl -X POST "http://localhost:8514/admin/keys?token=admin_secret_token_dev" \
  -H "Content-Type: application/json" \
  -d '{
    "source_path": "user1",
    "permissions": ["chat"],
    "expires_days": 30
  }'
```

#### 查看 API Key 列表

```bash
curl "http://localhost:8514/admin/keys?token=admin_secret_token_dev"
```

#### 查看审计日志

```bash
curl "http://localhost:8514/admin/logs?token=admin_secret_token_dev&limit=10"
```

#### 查看统计指标

```bash
curl "http://localhost:8514/admin/metrics?token=admin_secret_token_dev"
```

### 网关接口认证

API网关支持两种认证方式：

#### 方式1: X-API-Key Header

```bash
curl -H "X-API-Key: your_api_key_here" \
     -H "Content-Type: application/json" \
     "http://localhost:8514/proxy/miniai/v2/chat/completions"
```

#### 方式2: Authorization Bearer

```bash
curl -H "Authorization: Bearer your_api_key_here" \
     -H "Content-Type: application/json" \
     "http://localhost:8514/proxy/miniai/v2/chat/completions"
```

## 配置说明

### 应用配置 (config/development.yaml)

```yaml
app:
  name: "M-FastGate"
  version: "0.1.0"
  debug: true
  host: "0.0.0.0"
  port: 8514

database:
  url: "sqlite:///./fastgate.db"
  echo: true

security:
  admin_token: "admin_secret_token_dev"
  key_prefix: "fg_"
  default_expiry_days: 365

# API网关配置
api_gateway:
  backend_url: "http://172.16.99.32:1030"
  backend_path: "/miniai/v2/chat/completions"
  real_api_key: "your_real_api_key_here"
  strip_headers:
    - "host"
    - "x-api-key"
    - "authorization"
    - "x-forwarded-for"
  async_audit: true
  timeout: 60
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
│   │   ├── api_key.py
│   │   └── audit_log.py
│   ├── api/                   # API 路由
│   │   ├── admin.py          # 管理接口
│   │   ├── gateway.py        # API网关接口
│   │   ├── proxy.py          # 代理接口（兼容）
│   │   └── ui.py             # Web管理界面
│   ├── services/              # 业务逻辑
│   │   ├── key_manager.py
│   │   ├── route_manager.py
│   │   ├── audit_service.py
│   │   └── api_gateway_service.py  # API网关服务
│   ├── middleware/            # 中间件
│   │   └── auth.py
│   ├── templates/             # Web界面模板
│   │   ├── base.html
│   │   └── dashboard.html
│   └── static/               # 静态文件
│       ├── css/admin.css
│       └── js/
│           ├── common.js
│           └── dashboard.js
├── config/                    # 配置文件
│   ├── development.yaml
│   └── routes.yaml
├── requirements.txt           # Python 依赖
├── create_api_keys.py        # API Key创建工具
├── test_gateway.py           # 网关测试脚本
└── README.md                 # 项目说明
```

## 开发说明

### 数据库

默认使用 SQLite 数据库，数据库文件会自动创建在项目根目录。

### 审计日志

异步审计日志会记录所有通过网关的请求，包括：
- 请求ID和API Key信息
- 来源路径和客户端信息
- 请求方法、路径和目标URL
- 响应状态码和时间统计
- 请求/响应数据大小
- 流式响应特殊标记

### API网关特性

- **统一端点**: 所有用户请求同一个端点
- **参数清洗**: 自动移除敏感请求头
- **固定Key转发**: 使用配置的real-key访问后端
- **异步审计**: 日志记录不阻塞业务请求
- **流式支持**: 完整支持SSE流式响应
- **错误处理**: 完善的异常处理和监控

## 测试验证

### 快速测试工具

```bash
# 创建测试API Key
python create_api_keys.py

# 运行网关测试
python test_gateway.py

# 检查服务健康状态
curl http://localhost:8514/health
```

### Web界面测试

1. 启动服务：`python -m uvicorn app.main:app --host 0.0.0.0 --port 8514 --reload`
2. 访问：`http://localhost:8514/admin/ui/?token=admin_secret_token_dev`
3. 在仪表板中创建API Key并测试

## 开发历程

### Phase 1: 基础网关功能
- ✅ API Key管理系统
- ✅ 基础代理转发
- ✅ 审计日志记录

### Phase 2: API网关增强
- ✅ 统一端点设计
- ✅ 异步详细审计
- ✅ 参数清洗转发
- ✅ Web管理界面

## 许可证

MIT License

## 贡献

欢迎提交 Issue 和 Pull Request！