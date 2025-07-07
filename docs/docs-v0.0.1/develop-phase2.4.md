# M-FastGate Phase 2.4 开发计划 - 智能模型路由系统

## 开发目标

基于 Phase 2.3 完成的界面优化，实现核心的智能路由功能。根据请求体中的 `model` 字段，动态路由到对应的模型服务端点，并自动添加必要的认证信息和元数据。

**业务背景：** 
- 前半部分已实现：用户通过API Key验证，请求进入M-FastGate
- 后半部分待实现：根据请求中的model字段，智能路由到对应的模型服务

**目标模型服务：**
1. **DeepSeekR1** - 通过云天代理 `10.101.32.14:34094/openapi/proxy/**` (100并发，32K/8K上下文，推荐温度0.6，Top P 0.95)
2. **QwQ-32B** - 通过云天代理 `10.101.32.14:34094/openapi/proxy/**` (100并发，120K/8K上下文)  
3. **Qwen2.5-32B-Instruct** - 通过云天代理 `10.101.32.14:34094/openapi/proxy/**` (100并发，120K/8K上下文)
4. **bge-large-zh-v1.5** - 通过云天代理 `10.101.32.14:34094/openapi/proxy/embed` (嵌入模型，输入≤512 tokens，输出1024维向量)

**开发重点：** 智能路由引擎 + 配置管理 + 请求增强  
**预估工期：** 5-7 个工作日  
**版本：** v0.0.1-phase2.4

## 系统架构设计

### 架构概览

**当前状态 (Phase 2.3 已完成)：**
```
[user1, user2] → API Key验证 → M-FastGate → 固定端点
```

**Phase 2.4 目标架构：**
```
用户请求 → API Key验证 → 模型路由解析 → 请求增强 → 云天代理调用 → 响应返回
    ↓                    ↓                ↓              ↓
[user1, user2] → M-FastGate → 云天代理(10.101.32.14:34094) → [DeepSeekR1, QwQ-32B, Qwen2.5, bge-large-zh]
                       ↑                    ↓
                 根据请求中的model字段    /openapi/proxy/** 或 /openapi/proxy/embed
                      智能路由
```

**核心转变：**
- **从：** 静态代理转发 → **到：** 基于model字段的动态智能路由  
- **增加：** 请求体和请求头的自动增强（appKey、systemSource、modelIp等）
- **支持：** 配置化的模型端点管理和健康检查

**路由规则：**
- **Chat模型** (DeepSeekR1, QwQ-32B, Qwen2.5-32B-Instruct) → `http://10.101.32.14:34094/openapi/proxy/**`
- **嵌入模型** (bge-large-zh-v1.5) → `http://10.101.32.14:34094/openapi/proxy/embed`
- **统一代理**：所有请求都通过云天代理服务(10.101.32.14:34094)转发到实际的模型服务

### 核心组件设计

#### 1. ModelRouteManager (模型路由管理器)
**职责：**
- 管理模型到端点的映射配置
- 提供模型路由查询接口
- 支持配置热重载

#### 2. RequestEnhancer (请求增强器)
**职责：**
- 自动添加认证头 (`appKey`)
- 注入元数据到请求体 (`systemSource`, `modelIp`, `modelPort`, `modelName`)
- 保持原始请求结构完整性

#### 3. IntelligentRouter (智能路由器)
**职责：**
- 解析请求体中的 `model` 字段
- 执行路由决策逻辑
- 处理路由失败的降级策略

#### 4. ConfigManager (配置管理器)
**职责：**
- 管理模型配置的加载和更新
- 支持环境变量和配置文件
- 提供配置验证功能

## 详细功能规格

### 1. 模型路由配置

#### 1.1 目标模型服务配置
根据用户提供的三个模型服务：

```yaml
# 云天代理服务配置
cloud_proxy:
  host: "10.101.32.14"
  port: 34094
  base_path: "/openapi/proxy"

model_endpoints:
  DeepSeekR1:
    model_name: "DeepSeekR1"
    endpoint_type: "chat"  # chat completion
    proxy_path: "/**"  # 会动态替换为具体的路径
    parameters:
      max_concurrency: 100
      context_length: "32K/8K"
      recommended_temperature: 0.6
      recommended_top_p: 0.95
    health_check_path: "/health"
    
  QwQ-32B:
    model_name: "QwQ-32B"
    endpoint_type: "chat"  # chat completion
    proxy_path: "/**"
    parameters:
      max_concurrency: 100
      context_length: "120K/8K"
    health_check_path: "/health"
    
  Qwen2.5-32B-Instruct:
    model_name: "Qwen2.5-32B-Instruct"
    endpoint_type: "chat"  # chat completion
    proxy_path: "/**"
    parameters:
      max_concurrency: 100
      context_length: "120K/8K"
    health_check_path: "/health"
    
  bge-large-zh-v1.5:
    model_name: "bge-large-zh-v1.5"
    endpoint_type: "embedding"  # embedding
    proxy_path: "/embed"
    parameters:
      max_input_tokens: 512
      output_dimensions: 1024
      embedding_type: "text"
    health_check_path: "/health"
    timeout: 20  # 嵌入模型通常响应较快

# 认证配置
authentication:
  app_key: "${MODEL_APP_KEY}"  # 从环境变量获取
  system_source: "${SYSTEM_SOURCE:智能客服系统}"  # 默认值为"智能客服系统"
```

#### 1.2 配置管理策略
**配置来源优先级：**
1. 环境变量 (最高优先级)
2. 配置文件 (`config/model_routes.yaml`)
3. 数据库配置表 (未来扩展)
4. 默认配置 (最低优先级)

**关键环境变量：**
```bash
MODEL_APP_KEY=your_app_key_here
SYSTEM_SOURCE=智能客服系统
MODEL_CONFIG_PATH=config/model_routes.yaml
ENABLE_MODEL_ROUTING=true
```

#### 1.3 实施步骤
**Phase 2.4 实施关键步骤：**

1. **数据库扩展** - 添加模型路由配置表和使用统计表
2. **核心服务开发** - 实现ModelRouteManager、RequestEnhancer、IntelligentRouter
3. **API接口升级** - 修改现有proxy接口，支持智能路由
4. **配置管理** - 创建模型路由配置文件和环境变量
5. **Web界面** - 添加模型路由管理页面
6. **测试验证** - 确保三个目标模型服务可正常路由和增强

**关键集成点：**
- 复用现有的API Key验证逻辑
- 扩展现有的审计日志，添加模型信息
- 保持现有的流式响应处理能力
- 确保向后兼容性

### 2. 路由逻辑设计

#### 2.1 请求解析流程
```python
# 伪代码示例
def route_request(request_body, headers):
    # 1. 解析model字段
    model_name = extract_model_from_request(request_body)
    
    # 2. 查找路由配置
    endpoint = model_route_manager.get_endpoint(model_name)
    
    # 3. 增强请求
    enhanced_request = request_enhancer.enhance(
        request_body, 
        endpoint,
        headers
    )
    
    # 4. 构建目标URL
    if endpoint.endpoint_type == "embedding":
        target_url = f"http://{cloud_proxy.host}:{cloud_proxy.port}{cloud_proxy.base_path}/embed"
    else:
        # chat completion models - 路径由原始请求路径决定
        target_url = f"http://{cloud_proxy.host}:{cloud_proxy.port}{cloud_proxy.base_path}{original_path}"
    
    return target_url, enhanced_request
```

#### 2.2 请求体增强逻辑
**原始请求体：**
```json
{
  "model": "DeepSeekR1",
  "messages": [...],
  "temperature": 0.7,
  "stream": true
}
```

**增强后请求体（Chat Completion模型）：**
```json
{
  "model": "DeepSeekR1",
  "messages": [...],
  "temperature": 0.7,
  "stream": true,
  "systemSource": "智能客服系统",
  "modelIp": "10.101.32.14",
  "modelPort": 34094,
  "modelName": "DeepSeekR1"
}
```

**增强后请求体（Embedding模型）：**
```json
{
  "model": "bge-large-zh-v1.5",
  "input": "要嵌入的文本内容",
  "systemSource": "智能客服系统",
  "modelIp": "10.101.32.14", 
  "modelPort": 34094,
  "modelName": "bge-large-zh-v1.5"
}
```

**增强后请求头：**
```
Content-Type: application/json
Authorization: Bearer [原始token]
appKey: [配置的appKey]
User-Agent: M-FastGate/0.0.1-phase2.4
X-Request-ID: [生成的请求ID]
```

### 3. 数据模型设计

#### 3.1 模型端点配置
```python
# app/models/model_endpoint.py
from pydantic import BaseModel
from typing import Optional, Dict, Any

class CloudProxyConfig(BaseModel):
    """云天代理服务配置"""
    host: str = "10.101.32.14"
    port: int = 34094
    base_path: str = "/openapi/proxy"

class ModelEndpointConfig(BaseModel):
    """模型端点配置"""
    model_name: str
    endpoint_type: str  # "chat" 或 "embedding"
    proxy_path: str  # "/**" 或 "/embed"
    parameters: Optional[Dict[str, Any]] = None
    health_check_path: str = "/health"
    timeout: int = 30
    max_retries: int = 3
    is_active: bool = True

class ModelRouteConfig(BaseModel):
    """模型路由配置响应"""
    id: str
    model_name: str
    endpoint_config: ModelEndpointConfig
    created_at: datetime
    updated_at: datetime
    
class ModelRouteCreate(BaseModel):
    """创建模型路由配置请求"""
    model_name: str
    endpoint_type: str  # "chat" 或 "embedding"
    proxy_path: str  # "/**" 或 "/embed"
    parameters: Optional[Dict[str, Any]] = None
```

#### 3.2 数据库表设计
```sql
-- 模型路由配置表
CREATE TABLE model_routes (
    id VARCHAR(50) PRIMARY KEY,
    model_name VARCHAR(100) NOT NULL UNIQUE,
    endpoint_type VARCHAR(20) NOT NULL,  -- 'chat' 或 'embedding'
    proxy_path VARCHAR(500) NOT NULL,    -- '/**' 或 '/embed'
    parameters JSONB,
    health_check_path VARCHAR(500) DEFAULT '/health',
    timeout INTEGER DEFAULT 30,
    max_retries INTEGER DEFAULT 3,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 模型使用统计表
CREATE TABLE model_usage_stats (
    id VARCHAR(50) PRIMARY KEY,
    model_name VARCHAR(100) NOT NULL,
    api_key VARCHAR(100),
    source_path VARCHAR(100),
    request_count INTEGER DEFAULT 1,
    total_tokens INTEGER DEFAULT 0,
    total_response_time_ms INTEGER DEFAULT 0,
    error_count INTEGER DEFAULT 0,
    date DATE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(model_name, api_key, source_path, date)
);

-- 索引
CREATE INDEX idx_model_routes_model_name ON model_routes(model_name);
CREATE INDEX idx_model_routes_active ON model_routes(is_active);
CREATE INDEX idx_model_usage_stats_model_date ON model_usage_stats(model_name, date);
```

### 4. 核心服务实现

#### 4.1 ModelRouteManager服务
```python
# app/services/model_route_manager.py
class ModelRouteManager:
    def __init__(self, db: Session):
        self.db = db
        self._config_cache = {}
        self._load_config()
    
    def get_endpoint(self, model_name: str) -> Optional[ModelEndpointConfig]:
        """获取模型端点配置"""
        # 优先从缓存获取
        if model_name in self._config_cache:
            return self._config_cache[model_name]
        
        # 从数据库查询
        route = self.db.query(ModelRouteDB).filter(
            ModelRouteDB.model_name == model_name,
            ModelRouteDB.is_active == True
        ).first()
        
        if route:
            config = ModelEndpointConfig(**route.__dict__)
            self._config_cache[model_name] = config
            return config
        
        return None
    
    def add_route(self, route_data: ModelRouteCreate) -> ModelRouteConfig:
        """添加模型路由"""
        route_id = f"route_{uuid.uuid4().hex[:12]}"
        route_db = ModelRouteDB(
            id=route_id,
            **route_data.dict()
        )
        self.db.add(route_db)
        self.db.commit()
        
        # 更新缓存
        self._refresh_cache()
        
        return ModelRouteConfig.from_orm(route_db)
    
    def update_route(self, model_name: str, route_data: ModelRouteCreate) -> Optional[ModelRouteConfig]:
        """更新模型路由"""
        route = self.db.query(ModelRouteDB).filter(
            ModelRouteDB.model_name == model_name
        ).first()
        
        if route:
            for key, value in route_data.dict(exclude_unset=True).items():
                setattr(route, key, value)
            route.updated_at = datetime.utcnow()
            self.db.commit()
            
            # 更新缓存
            self._refresh_cache()
            
            return ModelRouteConfig.from_orm(route)
        
        return None
    
    def _load_config(self):
        """加载配置到缓存"""
        routes = self.db.query(ModelRouteDB).filter(
            ModelRouteDB.is_active == True
        ).all()
        
        for route in routes:
            config = ModelEndpointConfig(**route.__dict__)
            self._config_cache[route.model_name] = config
```

#### 4.2 RequestEnhancer服务
```python
# app/services/request_enhancer.py
class RequestEnhancer:
    def __init__(self):
        self.app_key = settings.MODEL_APP_KEY
        self.system_source = settings.SYSTEM_SOURCE
    
    def enhance_request(
        self, 
        request_body: dict, 
        endpoint: ModelEndpointConfig,
        original_headers: dict
    ) -> Tuple[dict, dict]:
        """增强请求体和请求头"""
        
        # 增强请求体
        enhanced_body = request_body.copy()
        enhanced_body.update({
            "systemSource": self.system_source,
            "modelIp": settings.CLOUD_PROXY_HOST,  # 云天代理IP
            "modelPort": settings.CLOUD_PROXY_PORT,  # 云天代理端口
            "modelName": endpoint.model_name
        })
        
        # 增强请求头
        enhanced_headers = original_headers.copy()
        enhanced_headers.update({
            "appKey": self.app_key,
            "User-Agent": f"M-FastGate/{settings.VERSION}",
            "X-Forwarded-By": "M-FastGate"
        })
        
        return enhanced_body, enhanced_headers
```

#### 4.3 IntelligentRouter服务
```python
# app/services/intelligent_router.py
class IntelligentRouter:
    def __init__(self, db: Session):
        self.route_manager = ModelRouteManager(db)
        self.request_enhancer = RequestEnhancer()
        self.usage_tracker = ModelUsageTracker(db)
    
    async def route_request(
        self, 
        request_body: dict, 
        headers: dict,
        api_key: str,
        source_path: str
    ) -> RouteResult:
        """执行智能路由"""
        
        # 1. 提取模型名称
        model_name = self._extract_model_name(request_body)
        if not model_name:
            raise ValueError("Request body must contain 'model' field")
        
        # 2. 获取路由配置
        endpoint = self.route_manager.get_endpoint(model_name)
        if not endpoint:
            raise ValueError(f"No route configured for model: {model_name}")
        
        # 3. 增强请求
        enhanced_body, enhanced_headers = self.request_enhancer.enhance_request(
            request_body, endpoint, headers
        )
        
        # 4. 构建目标URL
        cloud_proxy = settings.CLOUD_PROXY_CONFIG
        if endpoint.endpoint_type == "embedding":
            target_url = f"http://{cloud_proxy.host}:{cloud_proxy.port}{cloud_proxy.base_path}/embed"
        else:
            # chat completion模型 - 保持原始请求路径
            original_path = request.url.path.replace("/proxy", "")
            target_url = f"http://{cloud_proxy.host}:{cloud_proxy.port}{cloud_proxy.base_path}{original_path}"
        
        # 5. 记录使用统计
        await self.usage_tracker.track_request(
            model_name, api_key, source_path
        )
        
        return RouteResult(
            target_url=target_url,
            enhanced_body=enhanced_body,
            enhanced_headers=enhanced_headers,
            endpoint_config=endpoint
        )
    
    def _extract_model_name(self, request_body: dict) -> Optional[str]:
        """从请求体中提取模型名称"""
        return request_body.get("model")
```

### 5. API 接口设计

#### 5.1 管理接口
```python
# app/api/model_routes.py
@router.get("/model-routes")
async def list_model_routes(
    db: Session = Depends(get_db),
    token: str = Depends(verify_admin_token)
) -> List[ModelRouteConfig]:
    """获取所有模型路由配置"""
    route_manager = ModelRouteManager(db)
    return route_manager.list_routes()

@router.post("/model-routes")
async def create_model_route(
    route_data: ModelRouteCreate,
    db: Session = Depends(get_db),
    token: str = Depends(verify_admin_token)
) -> ModelRouteConfig:
    """创建模型路由配置"""
    route_manager = ModelRouteManager(db)
    return route_manager.add_route(route_data)

@router.put("/model-routes/{model_name}")
async def update_model_route(
    model_name: str,
    route_data: ModelRouteCreate,
    db: Session = Depends(get_db),
    token: str = Depends(verify_admin_token)
) -> ModelRouteConfig:
    """更新模型路由配置"""
    route_manager = ModelRouteManager(db)
    result = route_manager.update_route(model_name, route_data)
    if not result:
        raise HTTPException(status_code=404, detail="Model route not found")
    return result

@router.delete("/model-routes/{model_name}")
async def delete_model_route(
    model_name: str,
    db: Session = Depends(get_db),
    token: str = Depends(verify_admin_token)
):
    """删除模型路由配置"""
    route_manager = ModelRouteManager(db)
    success = route_manager.delete_route(model_name)
    if not success:
        raise HTTPException(status_code=404, detail="Model route not found")
    return {"message": "Model route deleted successfully"}
```

#### 5.2 核心路由接口
```python
# app/api/proxy.py (修改现有的代理接口)
@router.post("/proxy/{path:path}")
async def intelligent_proxy(
    path: str,
    request: Request,
    db: Session = Depends(get_db)
):
    """智能代理接口 - 基于模型路由"""
    
    # 1. API Key 验证（复用现有逻辑）
    api_key = extract_api_key(request.headers)
    key_info = validate_api_key(db, api_key)
    
    # 2. 获取请求体
    request_body = await request.json()
    
    # 3. 执行智能路由
    router = IntelligentRouter(db)
    route_result = await router.route_request(
        request_body=request_body,
        headers=dict(request.headers),
        api_key=api_key,
        source_path=key_info.source_path
    )
    
    # 4. 转发请求到目标服务
    async with httpx.AsyncClient() as client:
        response = await client.post(
            route_result.target_url,
            json=route_result.enhanced_body,
            headers=route_result.enhanced_headers,
            timeout=route_result.endpoint_config.timeout
        )
    
    # 5. 记录审计日志（复用现有逻辑）
    await log_request(
        request_id=generate_request_id(),
        api_key=api_key,
        source_path=key_info.source_path,
        method=request.method,
        path=f"/proxy/{path}",
        target_url=route_result.target_url,
        status_code=response.status_code,
        request_body=route_result.enhanced_body,
        response_body=response.content,
        model_name=route_result.endpoint_config.model_name
    )
    
    return StreamingResponse(
        response.aiter_bytes(),
        status_code=response.status_code,
        headers=dict(response.headers)
    )
```

### 6. Web 管理界面

#### 6.1 模型路由管理页面
**新增页面：** `app/templates/model_routes.html`

**功能特性：**
- 模型路由配置列表展示
- 新增/编辑/删除模型路由
- 健康检查状态显示
- 使用统计图表
- 配置导入/导出功能

**页面布局：**
```html
<!-- 模型路由管理页面结构 -->
<div class="container-fluid">
    <!-- 页面标题和操作按钮 -->
    <div class="d-flex justify-content-between">
        <h1>模型路由管理</h1>
        <div>
            <button class="btn btn-primary" onclick="showAddRouteModal()">
                <i class="fas fa-plus"></i> 添加路由
            </button>
            <button class="btn btn-outline-info" onclick="refreshHealthStatus()">
                <i class="fas fa-heartbeat"></i> 健康检查
            </button>
        </div>
    </div>
    
    <!-- 路由配置列表 -->
    <div class="card">
        <div class="card-header">
            <h5>当前配置的模型路由</h5>
        </div>
        <div class="card-body">
            <table class="table table-hover">
                <thead>
                    <tr>
                        <th>模型名称</th>
                        <th>目标地址</th>
                        <th>健康状态</th>
                        <th>并发数</th>
                        <th>上下文长度</th>
                        <th>状态</th>
                        <th>操作</th>
                    </tr>
                </thead>
                <tbody id="routesTable">
                    <!-- 路由数据将通过 JavaScript 填充 -->
                </tbody>
            </table>
        </div>
    </div>
    
    <!-- 使用统计图表 -->
    <div class="row mt-4">
        <div class="col-md-6">
            <div class="card">
                <div class="card-header">
                    <h6>模型使用分布</h6>
                </div>
                <div class="card-body">
                    <canvas id="modelUsageChart"></canvas>
                </div>
            </div>
        </div>
        <div class="col-md-6">
            <div class="card">
                <div class="card-header">
                    <h6>响应时间趋势</h6>
                </div>
                <div class="card-body">
                    <canvas id="responseTimeChart"></canvas>
                </div>
            </div>
        </div>
    </div>
</div>

<!-- 添加/编辑路由模态框 -->
<div class="modal fade" id="routeModal" tabindex="-1">
    <div class="modal-dialog">
        <div class="modal-content">
            <div class="modal-header">
                <h5 class="modal-title">模型路由配置</h5>
                <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
            </div>
            <div class="modal-body">
                <form id="routeForm">
                    <div class="mb-3">
                        <label class="form-label">模型名称 *</label>
                        <input type="text" class="form-control" id="modelName" required>
                    </div>
                    <div class="row">
                        <div class="col-md-6">
                            <label class="form-label">端点类型 *</label>
                            <select class="form-control" id="endpointType" required>
                                <option value="chat">Chat Completion</option>
                                <option value="embedding">Embedding</option>
                            </select>
                        </div>
                        <div class="col-md-6">
                            <label class="form-label">代理路径 *</label>
                            <select class="form-control" id="proxyPath" required>
                                <option value="/**">/** (Chat模型)</option>
                                <option value="/embed">/embed (嵌入模型)</option>
                            </select>
                        </div>
                    </div>
                    <div class="mb-3">
                        <label class="form-label">云天代理信息</label>
                        <input type="text" class="form-control" value="10.101.32.14:34094/openapi/proxy" readonly>
                        <small class="text-muted">所有请求都通过云天代理服务转发</small>
                    </div>
                    <div class="mb-3">
                        <label class="form-label">模型参数 (JSON)</label>
                        <textarea class="form-control" id="parameters" rows="4" 
                                  placeholder='{"max_concurrency": 100, "context_length": "32K/8K"}'></textarea>
                    </div>
                </form>
            </div>
            <div class="modal-footer">
                <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">取消</button>
                <button type="button" class="btn btn-primary" onclick="saveRoute()">保存</button>
            </div>
        </div>
    </div>
</div>
```

#### 6.2 JavaScript 控制逻辑
**新增文件：** `app/static/js/model_routes.js`

```javascript
class ModelRoutesManager {
    constructor() {
        this.routes = [];
        this.init();
    }
    
    async init() {
        await this.loadRoutes();
        this.setupEventListeners();
        this.startHealthCheck();
    }
    
    async loadRoutes() {
        try {
            const response = await apiClient.get('/model-routes');
            if (response.ok) {
                this.routes = await response.json();
                this.renderRoutes();
            }
        } catch (error) {
            console.error('加载模型路由失败:', error);
            showAlert('加载模型路由失败: ' + error.message, 'danger');
        }
    }
    
    renderRoutes() {
        const tbody = document.getElementById('routesTable');
        if (!this.routes || this.routes.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="7" class="text-center text-muted">
                        暂无模型路由配置
                    </td>
                </tr>
            `;
            return;
        }
        
        const rows = this.routes.map(route => `
            <tr>
                <td>
                    <strong>${route.model_name}</strong>
                    <br><small class="text-muted">${route.id}</small>
                </td>
                <td>
                    <code>云天代理(10.101.32.14:34094)</code>
                    <br><small class="text-muted">/openapi/proxy${route.proxy_path}</small>
                    <br><span class="badge ${route.endpoint_type === 'chat' ? 'bg-primary' : 'bg-info'}">${route.endpoint_type}</span>
                </td>
                <td>
                    <span class="badge ${this.getHealthStatusClass(route.health_status)}">
                        ${this.getHealthStatusText(route.health_status)}
                    </span>
                </td>
                <td>${route.parameters?.max_concurrency || '-'}</td>
                <td>${route.parameters?.context_length || '-'}</td>
                <td>
                    <span class="badge ${route.is_active ? 'bg-success' : 'bg-secondary'}">
                        ${route.is_active ? '启用' : '禁用'}
                    </span>
                </td>
                <td>
                    <button class="btn btn-sm btn-outline-primary" 
                            onclick="editRoute('${route.model_name}')">
                        <i class="fas fa-edit"></i>
                    </button>
                    <button class="btn btn-sm btn-outline-danger" 
                            onclick="deleteRoute('${route.model_name}')">
                        <i class="fas fa-trash"></i>
                    </button>
                    <button class="btn btn-sm btn-outline-info" 
                            onclick="testRoute('${route.model_name}')">
                        <i class="fas fa-vial"></i>
                    </button>
                </td>
            </tr>
        `).join('');
        
        tbody.innerHTML = rows;
    }
    
    async saveRoute() {
        const formData = {
            model_name: document.getElementById('modelName').value,
            endpoint_type: document.getElementById('endpointType').value,
            proxy_path: document.getElementById('proxyPath').value,
            parameters: this.parseParameters()
        };
        
        try {
            const isEdit = this.currentEditingRoute !== null;
            const url = isEdit ? `/model-routes/${this.currentEditingRoute}` : '/model-routes';
            const method = isEdit ? 'PUT' : 'POST';
            
            const response = await apiClient[method.toLowerCase()](url, formData);
            
            if (response.ok) {
                showAlert(`模型路由${isEdit ? '更新' : '创建'}成功！`, 'success');
                bootstrap.Modal.getInstance(document.getElementById('routeModal')).hide();
                await this.loadRoutes();
            } else {
                throw new Error(`HTTP ${response.status}`);
            }
        } catch (error) {
            console.error('保存模型路由失败:', error);
            showAlert('保存模型路由失败: ' + error.message, 'danger');
        }
    }
}

// 初始化
let modelRoutesManager;
document.addEventListener('DOMContentLoaded', () => {
    modelRoutesManager = new ModelRoutesManager();
});
```

### 7. 配置文件模板

#### 7.1 初始配置文件
**新增文件：** `config/model_routes.yaml`

```yaml
# M-FastGate 模型路由配置
version: "1.0"
last_updated: "2024-01-01T00:00:00Z"

# 认证配置
authentication:
  app_key: "${MODEL_APP_KEY}"
  system_source: "${SYSTEM_SOURCE:智能客服系统}"

# 默认配置
defaults:
  timeout: 30
  max_retries: 3
  health_check_interval: 60  # 秒
  health_check_timeout: 10   # 秒

# 模型端点配置
model_endpoints:
  DeepSeekR1:
    host: "10.101.32.26"
    port: 61025
    model_name: "DeepSeekR1"
    path: "/v1/chat/completions"
    parameters:
      max_concurrency: 100
      context_length: "32K/8K"
      recommended_temperature: 0.6
      recommended_top_p: 0.95
    health_check_path: "/health"
    timeout: 60  # DeepSeek 可能需要更长时间
    is_active: true
    
  QwQ-32B:
    host: "10.101.32.26"
    port: 51025
    model_name: "QwQ-32B"
    path: "/v1/chat/completions"
    parameters:
      max_concurrency: 100
      context_length: "120K/8K"
    health_check_path: "/health"
    timeout: 45
    is_active: true
    
  Qwen2.5-32B-Instruct:
    host: "10.101.32.26"
    port: 41025
    model_name: "Qwen2.5-32B-Instruct"
    path: "/v1/chat/completions"
    parameters:
      max_concurrency: 100
      context_length: "120K/8K"
    health_check_path: "/health"
    timeout: 45
    is_active: true

# 路由策略配置
routing:
  default_strategy: "round_robin"  # round_robin, least_connections, weighted
  fallback_enabled: true
  fallback_model: "Qwen2.5-32B-Instruct"  # 默认模型
  load_balancing: false  # 单个模型多实例时启用
  
# 监控配置
monitoring:
  enable_health_check: true
  health_check_interval: 60
  enable_usage_stats: true
  stats_aggregation_interval: 300  # 5分钟聚合一次
```

#### 7.2 环境变量配置模板
**新增文件：** `.env.example`

```bash
# M-FastGate Phase 2.4 Configuration

# 基础配置
DATABASE_URL=sqlite:///./app.db
SECRET_KEY=your-secret-key-here
ADMIN_TOKEN=admin_secret_token_dev

# 云天代理服务配置
CLOUD_PROXY_HOST=10.101.32.14
CLOUD_PROXY_PORT=34094
CLOUD_PROXY_BASE_PATH=/openapi/proxy

# 模型路由配置
ENABLE_MODEL_ROUTING=true
MODEL_APP_KEY=your-model-app-key-here
SYSTEM_SOURCE=智能客服系统
MODEL_CONFIG_PATH=config/model_routes.yaml

# 健康检查配置
HEALTH_CHECK_ENABLED=true
HEALTH_CHECK_INTERVAL=60
HEALTH_CHECK_TIMEOUT=10

# 日志配置
LOG_LEVEL=INFO
LOG_FORMAT=json
LOG_FILE=logs/fastgate.log

# 性能配置
MAX_CONCURRENT_REQUESTS=1000
REQUEST_TIMEOUT=60
RESPONSE_TIMEOUT=120

# 监控配置
ENABLE_METRICS=true
METRICS_PORT=9090
```

### 8. 数据库迁移脚本

#### 8.1 创建迁移文件
**新增文件：** `migrations/add_model_routes.sql`

```sql
-- Phase 2.4: 添加模型路由功能相关表

-- 模型路由配置表
CREATE TABLE IF NOT EXISTS model_routes (
    id VARCHAR(50) PRIMARY KEY,
    model_name VARCHAR(100) NOT NULL UNIQUE,
    host VARCHAR(255) NOT NULL,
    port INTEGER NOT NULL,
    path VARCHAR(500) DEFAULT '/v1/chat/completions',
    parameters JSONB,
    health_check_path VARCHAR(500) DEFAULT '/health',
    timeout INTEGER DEFAULT 30,
    max_retries INTEGER DEFAULT 3,
    is_active BOOLEAN DEFAULT TRUE,
    health_status VARCHAR(20) DEFAULT 'unknown',
    last_health_check TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 模型使用统计表
CREATE TABLE IF NOT EXISTS model_usage_stats (
    id VARCHAR(50) PRIMARY KEY,
    model_name VARCHAR(100) NOT NULL,
    api_key VARCHAR(100),
    source_path VARCHAR(100),
    request_count INTEGER DEFAULT 1,
    total_tokens INTEGER DEFAULT 0,
    total_response_time_ms INTEGER DEFAULT 0,
    error_count INTEGER DEFAULT 0,
    success_count INTEGER DEFAULT 0,
    date DATE NOT NULL,
    hour INTEGER NOT NULL CHECK (hour >= 0 AND hour <= 23),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(model_name, api_key, source_path, date, hour)
);

-- 审计日志表添加模型相关字段
ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS model_name VARCHAR(100);
ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS routing_time_ms INTEGER DEFAULT 0;

-- 索引
CREATE INDEX IF NOT EXISTS idx_model_routes_model_name ON model_routes(model_name);
CREATE INDEX IF NOT EXISTS idx_model_routes_active ON model_routes(is_active);
CREATE INDEX IF NOT EXISTS idx_model_routes_health ON model_routes(health_status);

CREATE INDEX IF NOT EXISTS idx_model_usage_stats_model_date ON model_usage_stats(model_name, date);
CREATE INDEX IF NOT EXISTS idx_model_usage_stats_api_key ON model_usage_stats(api_key);
CREATE INDEX IF NOT EXISTS idx_model_usage_stats_hour ON model_usage_stats(date, hour);

CREATE INDEX IF NOT EXISTS idx_audit_logs_model_name ON audit_logs(model_name);

-- 插入初始模型路由配置
INSERT INTO model_routes (id, model_name, endpoint_type, proxy_path, parameters, is_active) VALUES
('route_deepseekr1', 'DeepSeekR1', 'chat', '/**', '{"max_concurrency": 100, "context_length": "32K/8K", "recommended_temperature": 0.6, "recommended_top_p": 0.95}', true),
('route_qwq32b', 'QwQ-32B', 'chat', '/**', '{"max_concurrency": 100, "context_length": "120K/8K"}', true),
('route_qwen25_32b', 'Qwen2.5-32B-Instruct', 'chat', '/**', '{"max_concurrency": 100, "context_length": "120K/8K"}', true),
('route_bge_large_zh', 'bge-large-zh-v1.5', 'embedding', '/embed', '{"max_input_tokens": 512, "output_dimensions": 1024}', true);

-- 添加触发器更新 updated_at 字段
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_model_routes_updated_at BEFORE UPDATE ON model_routes FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_model_usage_stats_updated_at BEFORE UPDATE ON model_usage_stats FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
```

### 9. 测试和验证计划

#### 9.1 单元测试
```python
# tests/test_model_routing.py
import pytest
from app.services.intelligent_router import IntelligentRouter
from app.services.model_route_manager import ModelRouteManager

class TestModelRouting:
    
    def test_extract_model_name_from_request(self):
        """测试从请求体中提取模型名称"""
        router = IntelligentRouter(mock_db)
        
        request_body = {
            "model": "DeepSeekR1",
            "messages": [{"role": "user", "content": "Hello"}]
        }
        
        model_name = router._extract_model_name(request_body)
        assert model_name == "DeepSeekR1"
    
    def test_route_request_success(self):
        """测试成功路由请求"""
        router = IntelligentRouter(mock_db)
        
        request_body = {"model": "DeepSeekR1", "messages": []}
        headers = {"Authorization": "Bearer test"}
        
        result = await router.route_request(request_body, headers, "test_key", "user1")
        
        assert result.target_url == "http://10.101.32.26:61025/v1/chat/completions"
        assert "systemSource" in result.enhanced_body
        assert "modelIp" in result.enhanced_body
        assert "appKey" in result.enhanced_headers
    
    def test_route_request_unknown_model(self):
        """测试未知模型路由失败"""
        router = IntelligentRouter(mock_db)
        
        request_body = {"model": "UnknownModel", "messages": []}
        headers = {}
        
        with pytest.raises(ValueError, match="No route configured"):
            await router.route_request(request_body, headers, "test_key", "user1")
```

#### 9.2 集成测试
```python
# tests/test_integration.py
async def test_end_to_end_routing():
    """端到端路由测试"""
    # 1. 创建测试API Key
    # 2. 发送包含模型字段的请求
    # 3. 验证请求被正确路由到目标服务
    # 4. 验证请求体和请求头被正确增强
    # 5. 验证审计日志记录了模型信息
    pass

async def test_health_check_integration():
    """健康检查集成测试"""
    # 1. 配置模型端点
    # 2. 执行健康检查
    # 3. 验证健康状态更新
    # 4. 测试不健康端点的处理
    pass
```

#### 9.3 性能测试
```python
# tests/test_performance.py
async def test_routing_performance():
    """路由性能测试"""
    # 测试大量并发请求的路由性能
    # 验证缓存机制的有效性
    # 测试数据库查询性能
    pass

async def test_load_balancing():
    """负载均衡测试"""
    # 测试多个相同模型实例的负载均衡
    # 验证故障转移机制
    pass
```

### 10. 部署和监控

#### 10.1 部署清单
- [ ] 数据库迁移执行
- [ ] 环境变量配置
- [ ] 配置文件部署
- [ ] 服务重启
- [ ] 健康检查验证
- [ ] 路由功能测试
- [ ] 监控指标验证

#### 10.2 监控指标
- 模型路由成功率
- 各模型响应时间分布
- 模型使用统计
- 健康检查状态
- 错误率和异常监控

#### 10.3 告警配置
- 模型服务不可用告警
- 路由失败率过高告警
- 响应时间异常告警
- 配置加载失败告警

## 开发任务清单

### Phase 2.4 具体开发任务

#### 后端开发任务
- [ ] **数据库迁移** 
  - [ ] 创建model_routes表（更新字段：endpoint_type, proxy_path）
  - [ ] 创建model_usage_stats表  
  - [ ] 为audit_logs表添加model_name字段
  - [ ] 插入四个初始模型配置（3个Chat + 1个Embedding）

- [ ] **核心服务实现**
  - [ ] ModelRouteManager服务 (路由配置管理)
  - [ ] RequestEnhancer服务 (请求体和请求头增强)
  - [ ] IntelligentRouter服务 (智能路由逻辑)
  - [ ] ModelUsageTracker服务 (使用统计跟踪)

- [ ] **API接口开发**
  - [ ] 管理接口：/model-routes (CRUD)
  - [ ] 修改现有/proxy接口，集成智能路由
  - [ ] 健康检查接口
  - [ ] 使用统计查询接口

- [ ] **配置管理**
  - [ ] 创建config/model_routes.yaml配置文件
  - [ ] 环境变量配置和验证
  - [ ] 配置热重载机制

#### 前端开发任务
- [ ] **模型路由管理页面**
  - [ ] app/templates/model_routes.html
  - [ ] app/static/js/model_routes.js
  - [ ] 路由配置的增删改查界面
  - [ ] 健康状态监控界面
  - [ ] 使用统计图表展示

- [ ] **导航菜单更新**
  - [ ] 在base.html中添加模型路由管理链接
  - [ ] 在ui.py中添加路由管理页面路由

#### 测试和验证任务
- [ ] **单元测试**
  - [ ] 模型路由逻辑测试
  - [ ] 请求增强功能测试
  - [ ] 配置管理测试

- [ ] **集成测试**
  - [ ] 端到端路由测试
  - [ ] 四个目标模型服务连通性测试（3个Chat + 1个Embedding）
  - [ ] 请求体和请求头增强验证
  - [ ] 云天代理服务连通性测试

- [ ] **部署验证**
  - [ ] 环境变量配置验证  
  - [ ] 数据库迁移验证
  - [ ] 模型服务健康检查验证

## 总结

Phase 2.4 将为 M-FastGate 添加核心的智能路由功能，使其能够根据请求中的模型字段动态路由到不同的后端服务。这个功能将大大提升系统的灵活性和可扩展性，为后续的负载均衡、故障转移等高级功能奠定基础。

**关键交付物：**
1. 完整的模型路由管理系统
2. 智能路由引擎  
3. Web管理界面
4. 详细的配置管理
5. 健康检查和监控
6. 完善的测试覆盖

**技术亮点：**
- 基于model字段的动态路由，支持无缝扩展新模型
- 自动请求增强，减少客户端集成复杂度
- 完整的配置化管理，支持热重载
- 详细的使用统计和健康监控

**下一阶段展望 (Phase 2.5)：**
- 负载均衡和故障转移
- 更高级的路由策略
- 性能优化和缓存
- API限流和配额管理 