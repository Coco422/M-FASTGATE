 # M-FastGate v0.2.0 重构设计文档

## 重构背景与原因

### 当前版本(v0.0.1)存在的问题

1. **开发规范混乱**
   - 项目结构不统一，缺乏清晰的代码组织规范
   - 配置文件过多且分散（development.yaml, production.yaml, routes.yaml等）
   - 缺乏统一的配置管理策略

2. **数据库设计偏离**
   - Phase 2.4的设计在audit_logs表中添加了model_name等字段，违背了单一职责原则
   - 审计日志表应该专注于HTTP请求记录，而不是业务逻辑相关字段
   - 这种设计会导致技术债务累积

3. **功能局限性**
   - 路由配置表设计过于简单，无法支持复杂的代理场景
   - 缺乏通用的反向代理能力
   - 流式响应处理不够完善

## v0.2.0 设计目标

### 核心功能
1. **API Key管理** - 统一的密钥管理体系
2. **通用反向代理** - 类似nginx的代理转发能力  
3. **异步审计日志** - 完整记录HTTP请求响应过程
4. **流式响应支持** - 兼容OpenAI风格的流式API

### 设计原则
- **单一职责** - 每个模块职责明确，避免功能耦合
- **配置统一** - 使用单一YAML配置文件
- **结构清晰** - 代码组织规范，层次分明
- **扩展性强** - 支持灵活的路由配置和扩展

## 数据库重新设计

### 表结构简化

#### 1. api_keys - API Key管理表（保持不变）
```sql
CREATE TABLE api_keys (
    key_id VARCHAR(50) PRIMARY KEY,           -- API Key ID
    key_value VARCHAR(100) UNIQUE NOT NULL,   -- API Key值  
    source_path VARCHAR(100) NOT NULL,        -- 来源标识
    permissions TEXT DEFAULT '[]',            -- 权限列表
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    expires_at DATETIME,                      -- 过期时间
    is_active BOOLEAN DEFAULT TRUE,           -- 是否激活
    usage_count INTEGER DEFAULT 0,           -- 使用次数
    rate_limit INTEGER,                      -- 速率限制
    last_used_at DATETIME                    -- 最后使用时间
);
```

#### 2. audit_logs - HTTP请求审计表（简化，去除业务字段）
```sql
CREATE TABLE audit_logs (
    id VARCHAR(50) PRIMARY KEY,               -- 日志ID
    request_id VARCHAR(50) NOT NULL,          -- 请求ID
    api_key VARCHAR(100),                     -- 使用的API Key
    source_path VARCHAR(100),                 -- 来源路径
    method VARCHAR(10) NOT NULL,              -- HTTP方法
    path VARCHAR(500) NOT NULL,               -- 请求路径
    target_url VARCHAR(500),                  -- 目标URL  
    status_code INTEGER,                      -- HTTP状态码
    request_time DATETIME NOT NULL,           -- 请求开始时间
    first_response_time DATETIME,             -- 最早响应时间（流式响应的首个数据块时间）
    response_time DATETIME,                   -- 响应完成时间
    response_time_ms INTEGER,                 -- 响应时间（毫秒）
    request_size INTEGER DEFAULT 0,           -- 请求大小
    response_size INTEGER DEFAULT 0,          -- 响应大小
    user_agent VARCHAR(500),                  -- 用户代理
    ip_address VARCHAR(50),                   -- 客户端IP
    is_stream BOOLEAN DEFAULT FALSE,          -- 是否流式响应
    stream_chunks INTEGER DEFAULT 0,          -- 流式块数
    error_message TEXT,                       -- 错误信息
    request_headers TEXT,                     -- 请求头（可选记录）
    request_body TEXT,                        -- 请求体（可选记录）
    response_headers TEXT,                    -- 响应头（可选记录）
    response_body TEXT,                       -- 响应体（可选记录）
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP -- 创建时间（中国时区 UTC+8）
);
```

#### 3. proxy_routes - 通用代理路由配置表（重新设计）
```sql
CREATE TABLE proxy_routes (
    route_id VARCHAR(50) PRIMARY KEY,         -- 路由ID
    route_name VARCHAR(100) NOT NULL,         -- 路由名称
    description TEXT,                         -- 路由描述
    
    -- 匹配规则
    match_path VARCHAR(500) NOT NULL,         -- 匹配路径模式，如：/v1/*
    match_method VARCHAR(20) DEFAULT 'ANY',   -- 匹配HTTP方法，如：POST,GET,ANY
    match_headers TEXT,                       -- 匹配请求头条件（JSON）
    match_body_schema TEXT,                   -- 匹配请求体结构（JSON Schema）
    
    -- 目标配置  
    target_host VARCHAR(200) NOT NULL,        -- 目标主机，如：172.16.99.204:3398
    target_path VARCHAR(500) NOT NULL,        -- 目标路径，如：/v1/chat/completions
    target_protocol VARCHAR(10) DEFAULT 'http', -- 协议：http/https
    
    -- 转换规则
    strip_path_prefix BOOLEAN DEFAULT FALSE,  -- 是否剔除路径前缀
    add_headers TEXT,                         -- 新增请求头（JSON）
    add_body_fields TEXT,                     -- 新增请求体字段（JSON）
    remove_headers TEXT,                      -- 移除请求头列表（JSON数组）
    
    -- 其他配置
    timeout INTEGER DEFAULT 30,              -- 超时时间（秒）
    retry_count INTEGER DEFAULT 0,           -- 重试次数
    is_active BOOLEAN DEFAULT TRUE,           -- 是否启用
    priority INTEGER DEFAULT 100,            -- 优先级（数字越小优先级越高）
    
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP, -- 创建时间（中国时区 UTC+8）
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP  -- 更新时间（中国时区 UTC+8）
);
```

### 删除的表
- `route_configs` - 功能合并到proxy_routes
- `model_routes` - 移除业务逻辑相关表
- `model_usage_stats` - 移除业务统计表

## API重新设计

### API分层结构

#### 1. 核心代理接口
- `ANY /{path:path}` - 通用代理入口，根据路由配置转发

#### 2. 管理接口 (/admin)
- `/admin/keys/*` - API Key管理
- `/admin/routes/*` - 代理路由管理  
- `/admin/logs/*` - 审计日志查询
- `/admin/metrics/*` - 系统指标

#### 3. 系统接口
- `/health` - 健康检查
- `/metrics` - 运行指标（Prometheus格式）

## 路由匹配与转发逻辑

### 1. 路径匹配语法
```
/v1/*           - 匹配 /v1/ 开头的所有路径
/api/v2/**      - 匹配 /api/v2/ 开头的所有路径（包括子路径）
/exact/path     - 精确匹配
/user/{id}      - 参数匹配（id为路径参数）
/file/*.json    - 扩展名匹配
```

### 2. 请求转发流程
```
1. 接收请求 -> API Key验证 -> 路由匹配（按优先级）
2. 应用转换规则（添加/删除请求头、修改请求体等）
3. 异步记录审计日志（初始记录）
4. 转发到目标服务器
5. 处理响应（支持流式）
6. 更新审计日志（完整记录）
7. 返回响应给客户端
```

### 3. 流式响应处理策略

#### 识别流式请求
```python
def is_stream_request(request_body: dict) -> bool:
    """判断是否为流式请求"""
    # OpenAI风格
    if request_body.get("stream") is True:
        return True
    
    # 其他流式标识
    content_type = request.headers.get("content-type", "")
    if "text/event-stream" in content_type:
        return True
        
    return False
```

#### 流式响应处理
```python
async def handle_stream_response(response):
    """处理流式响应"""
    chunk_count = 0
    total_size = 0
    
    async def stream_wrapper():
        nonlocal chunk_count, total_size
        
        async for chunk in response.aiter_bytes():
            chunk_count += 1
            total_size += len(chunk)
            yield chunk
    
    # 返回流式响应包装器，同时记录统计信息
    return StreamingResponse(
        stream_wrapper(),
        status_code=response.status_code,
        headers=dict(response.headers),
        media_type="text/event-stream"
    )
```

## 配置文件统一

### 单一配置文件: config.yaml
```yaml
# M-FastGate v0.2.0 配置文件

app:
  name: "M-FastGate"
  version: "0.2.0"
  host: "0.0.0.0"
  port: 8514
  debug: false
  
database:
  url: "sqlite:///app/data/fastgate.db"
  echo: false
  pool_size: 10
  
security:
  admin_token: "${FASTGATE_ADMIN_TOKEN}"
  key_prefix: "fg_"
  default_expiry_days: 365
  rate_limit_enabled: true
  
logging:
  level: "INFO"
  file: "logs/fastgate.log"
  max_size: "100MB"
  backup_count: 5
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
  
proxy:
  default_timeout: 300
  max_retries: 3
  stream_chunk_size: 8192
  audit_async: true
  audit_include_headers: true   # 是否记录请求/响应头
  audit_include_body: false     # 是否记录请求/响应体（可能很大）
  audit_body_max_size: 10240    # 记录请求/响应体的最大大小（字节）
  
cors:
  allow_origins: ["*"]
  allow_methods: ["*"]  
  allow_headers: ["*"]
  allow_credentials: true
```

## 技术实现要点

### 1. 时区设计统一
```python
# 继续使用现有的中国时区设计
from datetime import datetime, timezone, timedelta

china_tz = timezone(timedelta(hours=8))

def get_china_time():
    """获取中国时间"""
    return datetime.now(china_tz)

# 数据库中所有时间字段都使用中国时区
# 前端显示也统一使用中国时间，避免时区转换混乱
```

### 2. 异步审计设计
```python
class AsyncAuditService:
    """异步审计服务"""
    
    async def log_request_start(self, request_info):
        """记录请求开始"""
        # 立即写入基础信息，包含：
        # - request_time（请求开始时间）
        # - request_headers, request_body（可选）
        # - 其他请求相关字段
        # response相关字段为空
        
    async def log_first_response(self, request_id, first_response_time):
        """记录首次响应时间"""
        # 更新first_response_time字段
        # 对于流式响应，这是收到第一个数据块的时间
        # 对于非流式响应，这与response_time相同
        
    async def log_request_complete(self, request_id, response_info):
        """记录请求完成"""
        # 更新响应相关信息：
        # - response_time（响应完成时间）
        # - status_code, response_size
        # - response_headers, response_body（可选）
        # - is_stream, stream_chunks（流式响应）
        # - error_message（如果有错误）
        
    async def log_stream_chunk(self, request_id, chunk_size):
        """记录流式块信息"""
        # 增量更新：
        # - stream_chunks计数
        # - response_size累计
```

### 3. 路由匹配引擎
```python
class Routematcher:
    """路由匹配引擎"""
    
    def match_request(self, path: str, method: str, headers: dict, body: dict):
        """匹配请求到对应路由"""
        # 按优先级排序的路由规则匹配
        
    def apply_transforms(self, route_config, request):
        """应用路由转换规则"""
        # 修改请求头、请求体等
```

### 4. 统一配置设计
```python
class Config:
    """统一配置类"""
    
    def __init__(self):
        self.config = self.load_config()
    
    def load_config(self):
        """加载config.yaml配置"""
        with open("config.yaml", "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        
        # 环境变量覆盖
        self.apply_env_overrides(config)
        return config
    
    def apply_env_overrides(self, config):
        """应用环境变量覆盖"""
        # DATABASE_URL -> config.database.url
        if os.getenv("DATABASE_URL"):
            config["database"]["url"] = os.getenv("DATABASE_URL")
        
        # ADMIN_TOKEN -> config.security.admin_token  
        if os.getenv("ADMIN_TOKEN"):
            config["security"]["admin_token"] = os.getenv("ADMIN_TOKEN")

# 统一的config.yaml结构
unified_config = {
    "app": {
        "name": "M-FastGate",
        "version": "0.2.0", 
        "host": "0.0.0.0",
        "port": 8514,  # 保持现有端口
        "debug": True
    },
    "database": {
        "url": "sqlite:///./app/data/fastgate.db",  # 保持现有SQLite
        "echo": False
    },
    "security": {
        "admin_token": "admin_secret_token_dev",
        "key_prefix": "fg_",
        "default_expiry_days": 365
    },
    "logging": {
        "level": "INFO",
        "format": "json",
        "file": "logs/fastgate.log"
    },
    "rate_limiting": {
        "enabled": True,
        "default_requests_per_minute": 100
    },
    "proxy": {
        "timeout": 30,
        "max_retries": 3,
        "enable_streaming": True,
        "strip_headers": [
            "host", "x-api-key", "authorization", 
            "x-forwarded-for", "x-real-ip", "x-source-path",
            "user-agent", "content-length"
        ],
        "async_audit": True,
        "audit_full_request": True,
        "audit_full_response": True
    }
}
```

### 5. 代理转发引擎
```python
class ProxyEngine:
    """代理转发引擎"""
    
    async def forward_request(self, route_config, request):
        """转发请求"""
        # 支持HTTP/HTTPS
        # 支持流式/非流式响应
        # 异常处理和重试
```

## 重构步骤

### Phase 1: 数据库重构
1. 备份现有数据
2. 创建新表结构
3. 数据迁移脚本
4. 清理旧表

### Phase 2: 配置统一
1. 合并所有配置到config.yaml
2. 更新配置加载逻辑
3. 环境变量支持

### Phase 3: 核心代理重构
1. 实现新的路由匹配引擎
2. 重构代理转发逻辑
3. 完善流式响应处理

### Phase 4: API重构
1. 简化API结构
2. 重构管理接口
3. 更新文档

### Phase 5: 测试与优化
1. 单元测试
2. 集成测试
3. 性能优化

## 预期收益

1. **代码质量提升** - 结构清晰，职责明确
2. **维护成本降低** - 配置统一，逻辑简化
3. **扩展性增强** - 通用代理能力，支持更多场景
4. **性能优化** - 异步处理，流式响应支持
5. **技术债务清理** - 移除不合理设计，规范化开发

## 重构施工计划

### 发现的设计问题及修正

在分析源码过程中发现以下问题，需要回溯修正设计：

1. **审计日志字段名不一致**
   - 当前代码使用 `path` 字段，设计文档使用 `request_path`
   - 当前代码使用 `ip_address` 字段，设计文档使用 `client_ip`
   - **修正**: 保持与现有代码一致，使用 `path` 和 `ip_address`

2. **时间字段设计统一**
   - 当前代码已有 `get_china_time()` 函数支持中国时区
   - **设计确认**: 全部使用中国时间 (UTC+8)，包括存储和显示

3. **配置文件结构复杂度**
   - 当前有4个配置文件，包含复杂的嵌套结构
   - **修正**: 直接创建统一的config.yaml，简化配置管理

### 施工计划分阶段实施

#### Phase 1: 数据库结构重构 (估计2天)

**文件改动清单:**

 1. **`migrations/v0.2.0_database_refactor.sql`** (新建)
    - 创建数据库迁移脚本
    - 修改 `audit_logs` 表结构，添加 `first_response_time` 字段
    - 删除 `model_name` 和 `routing_time_ms` 字段 (Phase 2.4遗留)
    - 创建新的 `proxy_routes` 表
    - 删除废弃的 `model_routes` 和 `model_usage_stats` 表

2. **`app/models/audit_log.py`** (重大修改)
   - 移除 Phase 2.4 相关字段: `model_name`, `routing_time_ms`
   - 添加 `first_response_time` 字段
   - 修改字段注释，保持与数据库一致
   - 更新 Pydantic 模型

3. **`app/models/route_config.py`** (删除)
   - 整个文件将被删除，功能合并到新的 proxy_routes

4. **`app/models/model_endpoint.py`** (删除)
   - 整个文件将被删除，移除业务逻辑相关模型

5. **`app/models/proxy_route.py`** (新建)
   - 创建新的通用代理路由模型
   - 支持复杂的匹配规则和转换规则
   - 包含优先级和路由匹配逻辑

#### Phase 2: 配置系统重构 (估计1天)

**文件改动清单:**

1. **`config.yaml`** (新建)
   - 创建统一配置文件
   - 合并所有现有配置项
   - 添加新的代理相关配置

2. **`app/config.py`** (重大重构)
   - 简化配置类结构，移除复杂的嵌套配置类  
   - 直接使用统一的 config.yaml 文件
   - 添加配置验证逻辑，支持环境变量覆盖
   - 移除多文件配置逻辑，简化加载流程

3. **`config/development.yaml`** (删除)
4. **`config/production.yaml`** (删除)  
5. **`config/routes.yaml`** (删除)
6. **`config/routes_test.yaml`** (删除)

#### Phase 3: 核心服务重构 (估计3天)

**文件改动清单:**

1. **`app/services/proxy_engine.py`** (新建)
   - 实现通用代理转发引擎
   - 支持HTTP/HTTPS协议
   - 流式响应处理
   - 错误处理和重试机制

2. **`app/services/route_matcher.py`** (新建)
   - 实现路由匹配引擎
   - 支持路径模式匹配
   - 请求头和请求体匹配
   - 优先级排序

3. **`app/services/audit_service.py`** (重构)
   - 移除 Phase 2.4 相关代码
   - 添加 `first_response_time` 处理
   - 简化审计日志创建逻辑
   - 优化异步处理性能

4. **`app/services/intelligent_router.py`** (删除)
   - 移除模型路由相关代码

5. **`app/services/model_route_manager.py`** (删除)
   - 移除模型路由管理服务

6. **`app/services/api_gateway_service.py`** (删除)
   - 功能合并到通用代理引擎

7. **`app/services/dynamic_route_manager.py`** (重构)
   - 重命名为 `proxy_route_manager.py`
   - 适配新的代理路由模型
   - 简化路由管理逻辑

8. **`app/services/route_manager.py`** (删除)
   - 功能合并到新的路由管理器

#### Phase 4: API接口重构 (估计2天)

**文件改动清单:**

1. **`app/api/proxy.py`** (重大重构)
   - 移除 `/smart/` 接口
   - 重构 `/{path:path}` 为通用代理接口
   - 集成新的路由匹配和代理引擎
   - 简化错误处理逻辑

2. **`app/api/admin.py`** (部分重构)
   - 移除模型路由管理相关接口
   - 重构路由管理接口，适配新的代理路由
   - 更新审计日志查询接口

3. **`app/api/model_routes.py`** (删除)
   - 整个文件删除

4. **`app/api/gateway.py`** (删除)
   - 功能合并到通用代理接口

5. **`app/api/ui.py`** (小幅修改)
   - 更新管理界面路由引用
   - 修改模板变量

#### Phase 5: 应用入口和中间件调整 (估计1天)

**文件改动清单:**

1. **`app/main.py`** (重构)
   - 移除模型路由相关导入
   - 简化路由注册
   - 更新健康检查和根路径信息
   - 移除废弃的服务初始化

2. **`app/middleware/auth.py`** (小幅修改)
   - 保持现有认证逻辑
   - 优化性能

3. **`app/database.py`** (小幅修改)
   - 更新模型导入
   - 移除废弃模型引用

#### Phase 6: 前端界面和文档更新 (估计1天)

**文件改动清单:**

1. **`app/templates/`** (部分更新)
   - 更新管理界面，移除模型路由管理
   - 添加代理路由管理界面
   - 更新API文档引用

2. **`app/static/`** (部分更新)
   - 更新JavaScript，适配新的API结构

3. **`README.md`** (更新)
   - 更新项目介绍
   - 更新配置说明
   - 更新使用示例

### 风险评估与预案

#### 高风险项目
1. **数据库迁移** - 开发环境直接重构
   - 预案: 分步验证，必要时重新初始化数据库

2. **配置文件重构** - 可能影响现有部署
   - 预案: 向后兼容模式，渐进式迁移

#### 中等风险项目
1. **API接口变更** - 可能影响客户端
   - 预案: 保持关键接口向后兼容

2. **流式响应处理** - 复杂度较高
   - 预案: 充分测试，性能监控

### 测试策略

#### 单元测试
- 每个重构模块编写对应测试
- 重点测试路由匹配逻辑
- 测试审计日志完整性

#### 集成测试  
- 端到端代理转发测试
- 流式响应测试
- 性能基准测试

#### 回归测试
- 现有功能兼容性测试
- API接口兼容性测试
- 数据完整性验证

### 预计总工期: 10个工作日

各阶段可以并行开展部分工作，实际工期可能压缩到8天左右。

### 成功标准

1. **功能完整性** - 所有核心功能正常工作
2. **性能提升** - 响应时间优化10%以上  
3. **代码质量** - 代码复杂度降低，可维护性提升
4. **配置简化** - 配置文件数量减少75%
5. **技术债务** - 移除所有Phase 2.4遗留问题