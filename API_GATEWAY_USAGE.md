# M-FastGate API网关使用指南

## 概述

M-FastGate API网关是一个专门设计的多租户API转发系统，所有用户通过统一端点访问后端服务，系统自动处理认证、参数清洗、审计日志等功能。

## 架构设计

### 请求流程

```
用户请求 → API网关 → 后端服务
[多用户]   [统一端点]   [固定Key]
```

详细流程：
1. **用户认证**: 验证用户API Key
2. **参数清洗**: 移除敏感请求头信息
3. **后端转发**: 使用固定real-key访问后端
4. **响应处理**: 支持流式和普通响应
5. **异步审计**: 记录完整请求日志（不阻塞）

## 配置说明

### 基础配置 (config/development.yaml)

```yaml
app:
  name: "M-FastGate"
  version: "0.1.0" 
  port: 8514  # 推荐使用8514端口

# API网关专门配置
api_gateway:
  backend_url: "http://172.16.99.32:1030"          # 后端服务地址
  backend_path: "/miniai/v2/chat/completions"      # 后端API路径
  real_api_key: "your_real_api_key_here"          # 后端认证Key
  strip_headers:                                    # 需要清洗的请求头
    - "host"
    - "x-api-key"
    - "authorization"
    - "x-forwarded-for"
  async_audit: true                                # 异步审计开关
  timeout: 60                                      # 请求超时时间(秒)
```

### 重要配置项说明

- **backend_url**: 后端服务的基础URL
- **real_api_key**: 用于访问后端的真实API Key，需要保密
- **strip_headers**: 转发时会移除的敏感请求头
- **async_audit**: 建议开启，避免审计阻塞业务请求

## API使用方法

### 统一端点

**所有用户都使用相同的端点**：
```
POST http://your-server:8514/proxy/miniai/v2/chat/completions
```

### 认证方式

支持两种API Key认证方式：

#### 方式1: X-API-Key Header (推荐)
```bash
curl -X POST "http://localhost:8514/proxy/miniai/v2/chat/completions" \
  -H "X-API-Key: your_user_api_key" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-3.5-turbo",
    "messages": [{"role": "user", "content": "Hello"}]
  }'
```

#### 方式2: Authorization Bearer
```bash
curl -X POST "http://localhost:8514/proxy/miniai/v2/chat/completions" \
  -H "Authorization: Bearer your_user_api_key" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-3.5-turbo", 
    "messages": [{"role": "user", "content": "Hi"}]
  }'
```

## 支持的功能

### 1. 普通聊天请求

```bash
curl -X POST "http://localhost:8514/proxy/miniai/v2/chat/completions" \
  -H "X-API-Key: user1_key" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-3.5-turbo",
    "messages": [
      {"role": "system", "content": "You are a helpful assistant."},
      {"role": "user", "content": "What is FastAPI?"}
    ],
    "temperature": 0.7,
    "max_tokens": 100
  }'
```

### 2. 流式聊天请求

```bash
curl -X POST "http://localhost:8514/proxy/miniai/v2/chat/completions" \
  -H "X-API-Key: user2_key" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-3.5-turbo",
    "messages": [
      {"role": "user", "content": "Tell me a story"}
    ],
    "stream": true
  }'
```

### 3. 多轮对话

```bash
curl -X POST "http://localhost:8514/proxy/miniai/v2/chat/completions" \
  -H "X-API-Key: user3_key" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-3.5-turbo",
    "messages": [
      {"role": "user", "content": "What is Python?"},
      {"role": "assistant", "content": "Python is a programming language..."},
      {"role": "user", "content": "How to learn it?"}
    ]
  }'
```

## 参数处理机制

### 自动清洗的请求头

系统会自动移除以下敏感请求头：
- `host`: 原始主机信息
- `x-api-key`: 用户API Key（用于认证后移除）
- `authorization`: 用户认证信息（替换为real-key）
- `x-forwarded-for`: 代理转发信息

### 自动添加的请求头

- `Authorization: Bearer {real_api_key}`: 使用配置的真实Key
- `Content-Type`: 保持原有内容类型
- `User-Agent`: M-FastGate标识

### 透传的业务参数

所有业务相关的参数会原样透传：
- 请求体(JSON)完全透传
- 业务相关的Header保持不变
- 查询参数(如果有)会保留

## 错误处理

### 常见错误响应

#### 1. 认证失败 (401)
```json
{
  "detail": "Invalid or expired API Key"
}
```

#### 2. 后端服务不可用 (502)
```json
{
  "detail": "Backend service unavailable"
}
```

#### 3. 请求超时 (504)
```json
{
  "detail": "Gateway timeout"
}
```

#### 4. 参数错误 (400)
```json
{
  "detail": "Invalid request format"
}
```

## 审计日志

### 日志记录内容

系统会异步记录以下信息：
- **请求信息**: 时间、API Key、IP地址、User-Agent
- **业务信息**: 请求方法、路径、目标URL
- **性能信息**: 响应时间、请求/响应大小
- **状态信息**: HTTP状态码、错误信息
- **流式信息**: 是否流式、分块数量

### 查看审计日志

#### Web界面查看
访问管理界面：`http://localhost:8514/admin/ui/?token=admin_token`

#### API接口查看
```bash
curl "http://localhost:8514/admin/logs?token=admin_token&limit=10"
```

## 性能优化

### 异步处理

- **审计日志**: 使用`asyncio.create_task`异步记录
- **不阻塞业务**: 日志记录失败不影响正常请求
- **批量处理**: 支持批量日志写入优化

### 连接复用

- 使用持久化HTTP连接池
- 自动重试机制
- 连接超时控制

### 缓存机制

- API Key验证结果缓存
- 配置信息内存缓存
- 数据库连接池复用

## 监控指标

### 关键指标

通过Web界面或API可以查看：
- **请求总数**: 累计处理的请求数量
- **成功率**: 2xx状态码请求占比
- **平均响应时间**: 处理时间统计
- **错误分布**: 各种错误状态码统计
- **用户活跃度**: 各API Key使用情况

### 实时监控

Web管理界面提供：
- 实时请求记录
- 24小时趋势图表
- 系统状态监控
- 自动刷新功能

## 最佳实践

### 1. API Key管理

- **定期轮换**: 建议定期更新API Key
- **权限最小化**: 只分配必要的权限
- **使用标识**: 为每个用户设置清晰的source_path标识
- **监控使用**: 定期检查Key的使用情况

### 2. 性能优化

- **合理超时**: 根据业务需求设置timeout
- **错误重试**: 客户端实现合理的重试机制
- **连接复用**: 使用支持keep-alive的HTTP客户端
- **批量请求**: 避免频繁的小量请求

### 3. 安全建议

- **HTTPS**: 生产环境使用HTTPS
- **IP白名单**: 可配置允许的客户端IP
- **速率限制**: 根据需要实现速率限制
- **日志审计**: 定期审查访问日志

### 4. 运维监控

- **健康检查**: 定期检查`/health`端点
- **日志监控**: 关注错误日志和异常情况
- **性能指标**: 监控响应时间和成功率
- **容量规划**: 根据使用量规划资源

## 故障排除

### 常见问题

#### 1. 网关无响应
- 检查服务启动状态
- 确认端口8514可访问
- 查看服务日志输出

#### 2. 后端连接失败
- 检查backend_url配置
- 验证网络连通性
- 确认real_api_key有效

#### 3. 认证失败
- 确认API Key存在且未过期
- 检查Key格式和传递方式
- 查看audit日志了解详情

#### 4. 流式响应异常
- 检查客户端SSE支持
- 确认网络连接稳定
- 查看后端流式响应格式

### 调试方法

#### 启用详细日志
```yaml
database:
  echo: true  # 启用SQL日志

app:
  debug: true  # 启用调试模式
```

#### 查看实时日志
```bash
# 查看服务日志
tail -f logs/app.log

# 查看错误日志
tail -f logs/error.log
```

## 版本兼容性

### API版本
- 当前版本: v0.1.0
- 兼容OpenAI Chat Completions API格式
- 支持SSE流式响应标准

### 升级注意事项
- 配置文件格式可能变化
- 数据库结构可能更新
- API端点保持向后兼容

## 技术支持

### 文档资源
- [README.md](./README.md) - 项目总体介绍
- [WEB_UI_GUIDE.md](./WEB_UI_GUIDE.md) - Web界面使用指南
- [develop-phase2.md](./develop-phase2.md) - 开发日志

### 获取帮助
- API文档: http://localhost:8514/docs
- Web管理界面: http://localhost:8514/admin/ui/
- 健康检查: http://localhost:8514/health

---

**注意**: 本指南基于Phase 2开发完成的功能。如需了解更多技术细节，请参考相关技术文档。 