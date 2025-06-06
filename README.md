# M-FastGate - 高性能通用API网关

## 概述

M-FastGate 是一个轻量级、高性能的通用API网关系统，专为现代微服务架构设计。它提供类似nginx的反向代理能力，同时集成了API密钥管理、流式响应支持、完整审计日志和Web管理界面。

### 核心特性

🚀 **高性能流式响应** - 22ms首字节时间，超越上游性能  
🔐 **安全API密钥管理** - 完整的权限控制和使用统计  
🎯 **智能路由匹配** - 支持路径、方法、请求体规则匹配  
📊 **完整审计日志** - 三阶段日志记录，包含TTFB性能监控  
🌐 **Web管理界面** - 可视化配置管理和实时监控  
🔧 **OpenAI兼容** - 100%兼容OpenAI流式API格式  

## 快速开始

### 1. 环境要求

- Python 3.12+
- SQLite 3
- 推荐系统：Linux/macOS

### 2. 安装运行

```bash
# 克隆项目
git clone <repository-url>
cd M-FastGate

# 安装依赖
pip install -r requirements.txt

# 启动服务
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 3. 基础配置

编辑 `config/config.yaml`：

```yaml
server:
  host: "0.0.0.0"
  port: 8000

database:
  sqlite_path: "data/fastgate.db"

proxy:
  timeout: 30
  max_retries: 3
  async_audit: true
```

## 核心接口

### 1. 通用代理接口

**`ANY /{path:path}`** - 所有API请求的统一入口

```http
POST /v1/chat/completions
Authorization: Bearer fg_your_api_key
Content-Type: application/json

{
  "model": "gpt-3.5-turbo",
  "messages": [{"role": "user", "content": "Hello"}],
  "stream": true
}
```

**特性：**
- 支持所有HTTP方法（GET, POST, PUT, DELETE等）
- 自动路由匹配和转发
- API密钥验证和转换
- 完整的请求响应审计

### 2. API密钥管理

#### 创建API密钥
```http
POST /admin/keys
Content-Type: application/json

{
  "source_path": "openai-proxy",
  "permissions": ["chat", "completions"],
  "rate_limit": 1000,
  "expires_at": "2024-12-31T23:59:59"
}
```

#### 查询API密钥
```http
GET /admin/keys?source_path=openai-proxy&is_active=true
```

#### 删除API密钥
```http
DELETE /admin/keys/{key_id}
```

### 3. 代理路由管理

#### 创建路由规则
```http
POST /admin/routes
Content-Type: application/json

{
  "route_name": "OpenAI Chat API",
  "match_path": "/v1/chat/*",
  "match_method": "POST",
  "target_host": "api.openai.com",
  "target_path": "/v1/chat/completions",
  "target_protocol": "https",
  "add_headers": {
    "Authorization": "Bearer sk-your-openai-key"
  },
  "timeout": 60,
  "priority": 100
}
```

#### 路由列表和管理
```http
GET /admin/routes                    # 获取所有路由
GET /admin/routes/{route_id}         # 获取单个路由
PUT /admin/routes/{route_id}         # 更新路由
DELETE /admin/routes/{route_id}      # 删除路由
POST /admin/routes/{route_id}/toggle # 启用/禁用路由
POST /admin/routes/{route_id}/test   # 测试路由连通性
```

### 4. 审计日志查询

#### 查询请求日志
```http
GET /admin/logs?start_time=2024-01-01&end_time=2024-01-31&status_code=200&is_stream=true
```

#### 导出日志数据
```http
GET /admin/logs/export?format=csv&fields=method,path,status_code,response_time_ms
```

#### 获取日志详情
```http
GET /admin/logs/{log_id}
```

### 5. 统计指标

#### 实时系统指标
```http
GET /admin/metrics
```

响应示例：
```json
{
  "total_requests": 12580,
  "total_errors": 23,
  "success_rate": 99.82,
  "avg_response_time": 156.7,
  "active_api_keys": 15,
  "active_routes": 8,
  "last_hour_requests": 234
}
```

#### 按时间统计
```http
GET /admin/metrics/daily?days=7     # 最近7天统计
GET /admin/metrics/hourly?hours=24  # 最近24小时统计
```

## 使用案例

### 案例1：OpenAI API代理

**场景**：为OpenAI API提供统一访问入口，隐藏真实API密钥

#### 1. 创建API密钥
```bash
curl -X POST http://localhost:8000/admin/keys \
  -H "Content-Type: application/json" \
  -d '{
    "source_path": "openai-chat",
    "permissions": ["chat"],
    "rate_limit": 1000
  }'
```

#### 2. 配置路由规则
```bash
curl -X POST http://localhost:8000/admin/routes \
  -H "Content-Type: application/json" \
  -d '{
    "route_name": "OpenAI Chat Proxy",
    "match_path": "/v1/chat/*",
    "match_method": "POST",
    "target_host": "api.openai.com",
    "target_path": "/v1/chat/completions",
    "target_protocol": "https",
    "add_headers": {
      "Authorization": "Bearer sk-your-real-openai-key"
    },
    "timeout": 60
  }'
```

#### 3. 客户端调用
```python
import httpx

async def chat_with_openai():
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/v1/chat/completions",
            headers={
                "Authorization": "Bearer fg_generated_api_key",
                "Content-Type": "application/json"
            },
            json={
                "model": "gpt-3.5-turbo",
                "messages": [{"role": "user", "content": "Hello"}],
                "stream": True
            }
        )
        
        async for line in response.aiter_lines():
            print(line)
```

### 案例2：多后端负载均衡

**场景**：在多个AI模型服务之间进行负载均衡

#### 1. 配置多个路由
```bash
# 主要路由 - 高优先级
curl -X POST http://localhost:8000/admin/routes \
  -d '{
    "route_name": "Primary AI Service",
    "match_path": "/v1/chat/*",
    "target_host": "172.16.99.32:8514",
    "target_path": "/v1/chat/completions",
    "priority": 50
  }'

# 备用路由 - 低优先级
curl -X POST http://localhost:8000/admin/routes \
  -d '{
    "route_name": "Backup AI Service", 
    "match_path": "/v1/chat/*",
    "target_host": "172.16.99.33:8514",
    "target_path": "/v1/chat/completions",
    "priority": 100
  }'
```

### 案例3：API使用统计和监控

**场景**：监控API使用情况，生成使用报告

#### 1. 获取实时统计
```python
import httpx
import asyncio

async def get_api_stats():
    async with httpx.AsyncClient() as client:
        # 获取实时指标
        metrics = await client.get("http://localhost:8000/admin/metrics")
        print(f"成功率: {metrics.json()['success_rate']}%")
        print(f"平均响应时间: {metrics.json()['avg_response_time']}ms")
        
        # 获取最近请求日志
        logs = await client.get(
            "http://localhost:8000/admin/logs",
            params={"limit": 10, "order": "desc"}
        )
        
        for log in logs.json()["items"]:
            print(f"{log['path']} - {log['status_code']} - {log['response_time_ms']}ms")

asyncio.run(get_api_stats())
```

#### 2. 导出使用报告
```bash
# 导出CSV格式报告
curl "http://localhost:8000/admin/logs/export?format=csv&start_time=2024-01-01&end_time=2024-01-31" \
  -o api_usage_report.csv
```

### 案例4：V2 多模型智能路由

**场景**：根据请求体中的model字段，智能路由到不同的AI服务

#### 1. 配置多模型路由
```bash
# 配置 Qwen3-30B 模型路由
curl -X POST "http://localhost:8514/admin/routes?token=admin_secret_token_dev" \
  -H "Content-Type: application/json" \
  -d '{
    "route_name": "V2 Qwen3-30B Proxy",
    "description": "V2 代理路由 - 根据model值路由到Qwen3-30B服务",
    "match_path": "/v2*",
    "match_method": "POST",
    "match_body_schema": {"model": "mckj/Qwen3-30B-A3B"},
    "target_host": "172.16.99.204:3398",
    "target_path": "/v1/chat/completions",
    "target_protocol": "http",
    "add_headers": {
      "Authorization": "Bearer your-backend-api-key",
      "X-Proxy-Source": "M-FastGate-v0.2.0"
    },
    "priority": 40,
    "is_active": true
  }'

# 配置 fallback 路由
curl -X POST "http://localhost:8514/admin/routes?token=admin_secret_token_dev" \
  -H "Content-Type: application/json" \
  -d '{
    "route_name": "V2 Fallback Proxy",
    "description": "V2 fallback路由 - 处理其他model值的请求",
    "match_path": "/v2*",
    "match_method": "POST",
    "target_host": "172.16.99.32:8516",
    "target_path": "/v1/chat/completions",
    "priority": 80,
    "is_active": true
  }'
```

#### 2. 客户端调用示例
```python
import httpx
import asyncio

async def test_v2_routing():
    """测试V2智能路由功能"""
    async with httpx.AsyncClient() as client:
        
        # 使用 Qwen3-30B 模型 - 路由到 172.16.99.204:3398
        response1 = await client.post(
            "http://localhost:8514/v2/chat/completions",
            headers={
                "Authorization": "Bearer fg_your_api_key",
                "Content-Type": "application/json"
            },
            json={
                "model": "mckj/Qwen3-30B-A3B",
                "messages": [{"role": "user", "content": "Hello"}],
                "max_tokens": 100
            }
        )
        
        # 使用其他模型 - 路由到 fallback 服务
        response2 = await client.post(
            "http://localhost:8514/v2/chat/completions",
            headers={
                "Authorization": "Bearer fg_your_api_key",
                "Content-Type": "application/json"
            },
            json={
                "model": "other-model",
                "messages": [{"role": "user", "content": "Hello"}],
                "max_tokens": 100
            }
        )

# 流式请求示例
async def test_v2_streaming():
    """测试V2流式响应"""
    async with httpx.AsyncClient() as client:
        async with client.stream(
            "POST",
            "http://localhost:8514/v2/chat/completions",
            headers={
                "Authorization": "Bearer fg_your_api_key",
                "Content-Type": "application/json"
            },
            json={
                "model": "mckj/Qwen3-30B-A3B",
                "messages": [{"role": "user", "content": "讲个故事"}],
                "stream": True
            }
        ) as response:
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    print(line[6:])
```

#### 3. 路由规则说明
- **优先级匹配**：系统按priority从低到高匹配路由
- **请求体匹配**：根据`match_body_schema`精确匹配model字段
- **Fallback机制**：无匹配规则时使用fallback路由
- **保持兼容**：与v1路由完全兼容，客户端无需修改

### 案例5：流式API代理

**场景**：代理支持流式响应的AI服务

#### 1. 配置流式路由
```bash
curl -X POST http://localhost:8000/admin/routes \
  -d '{
    "route_name": "Streaming Chat API",
    "match_path": "/stream/*",
    "match_body_schema": {"properties": {"stream": {"const": true}}},
    "target_host": "your-ai-service.com",
    "target_path": "/v1/chat/completions",
    "timeout": 300
  }'
```

#### 2. 客户端流式调用
```python
async def stream_chat():
    async with httpx.AsyncClient(timeout=300) as client:
        async with client.stream(
            "POST",
            "http://localhost:8000/stream/chat",
            headers={"Authorization": "Bearer fg_your_key"},
            json={
                "model": "gpt-4",
                "messages": [{"role": "user", "content": "讲个故事"}],
                "stream": True
            }
        ) as response:
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    print(line[6:])  # 处理SSE数据
```

## Web管理界面

访问 `http://localhost:8000/admin/dashboard` 可以使用Web管理界面：

- **仪表板** - 实时系统状态和统计
- **API密钥管理** - 可视化密钥创建和管理
- **路由配置** - 图形化路由规则配置
- **审计日志** - 请求日志查询和分析
- **统计报表** - 使用趋势和性能分析

## 系统监控

### 健康检查
```bash
curl http://localhost:8000/health
```

### Prometheus指标
```bash
curl http://localhost:8000/metrics
```

### 日志监控
```bash
tail -f logs/fastgate.log
```

## 性能特性

### 流式响应性能
- **TTFB（首字节时间）**: 22ms（超越上游性能）
- **并发处理**: 支持数千并发连接
- **内存使用**: 优化的流式处理，低内存占用

### 审计日志性能
- **异步写入**: 不阻塞主请求处理
- **批量处理**: 提高数据库写入效率
- **三阶段记录**: 请求开始 → 首字节 → 完成

### 系统稳定性
- **错误恢复**: 完整的异常处理和重试机制
- **连接池**: HTTP连接复用，减少开销
- **内存管理**: 自动清理和垃圾回收

## 配置参考

### 路由匹配规则

| 语法 | 说明 | 示例 |
|------|------|------|
| `/v1/*` | 前缀匹配 | 匹配 `/v1/chat`, `/v1/completions` |
| `/api/v2/**` | 深度匹配 | 匹配 `/api/v2/user/profile` |
| `/exact/path` | 精确匹配 | 仅匹配 `/exact/path` |
| `/user/{id}` | 参数匹配 | 匹配 `/user/123`, `/user/abc` |
| `*.json` | 扩展名匹配 | 匹配所有 `.json` 文件 |

### 请求体匹配

```json
{
  "match_body_schema": {
    "type": "object",
    "properties": {
      "model": {"type": "string"},
      "stream": {"const": true}
    },
    "required": ["model"]
  }
}
```

### 请求转换

```json
{
  "add_headers": {
    "Authorization": "Bearer real-api-key",
    "X-Custom-Header": "value"
  },
  "add_body_fields": {
    "max_tokens": 2048,
    "temperature": 0.7
  },
  "remove_headers": ["X-Remove-This"]
}
```

## 故障排除

### 常见问题

1. **流式响应中断**
   - 检查目标服务timeout设置
   - 确认客户端支持持久连接

2. **API密钥验证失败**
   - 验证密钥格式（以`fg_`开头）
   - 检查密钥有效期和权限配置

3. **路由匹配不生效**
   - 确认路由优先级设置
   - 检查匹配规则语法

4. **性能问题**
   - 开启异步审计：`async_audit: true`
   - 调整连接池大小
   - 检查数据库索引

### 日志分析

```bash
# 查看错误日志
grep "ERROR" logs/fastgate.log

# 查看慢请求
grep "response_time_ms.*[5-9][0-9][0-9]" logs/fastgate.log

# 监控实时请求
tail -f logs/fastgate.log | grep "Request forwarded"
```

## 许可证

本项目采用MIT许可证。详细信息请查看 `LICENSE` 文件。

---

**M-FastGate v0.2.0** - 高性能、易使用、功能完整的API网关解决方案

更多技术文档请参考 `docs/` 目录。