# 数据库设计文档 - v0.2.2

## 数据库概述

本项目使用SQLite数据库，数据库文件位置：`app/data/fastgate.db`

数据库支持以下核心功能：
1. API Key管理
2. HTTP请求审计日志记录
3. 通用代理路由配置管理

## 数据表结构

### 1. api_keys - API Key管理表

```sql
CREATE TABLE api_keys (
    key_id VARCHAR(50) PRIMARY KEY,           -- API Key ID，格式：fg_xxxxxxxxxxxxx
    key_value VARCHAR(100) UNIQUE NOT NULL,   -- API Key值，格式：fg_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
    source_path VARCHAR(100) NOT NULL,        -- 来源路径标识
    permissions TEXT DEFAULT '[]',            -- 权限列表，JSON字符串格式
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP, -- 创建时间
    expires_at DATETIME,                      -- 过期时间，可为NULL表示永不过期
    is_active BOOLEAN DEFAULT TRUE,           -- 是否激活
    usage_count INTEGER DEFAULT 0,           -- 使用次数
    rate_limit INTEGER,                      -- 速率限制，可为NULL表示无限制
    last_used_at DATETIME                    -- 最后使用时间
);

-- 索引
CREATE INDEX idx_api_keys_key_value ON api_keys(key_value);
CREATE INDEX idx_api_keys_source_path ON api_keys(source_path);
CREATE INDEX idx_api_keys_is_active ON api_keys(is_active);
```

### 2. audit_logs - HTTP请求审计日志表

```sql
CREATE TABLE audit_logs (
    id VARCHAR(50) PRIMARY KEY,               -- 日志ID，格式：log_xxxxxxxxxxxxx
    request_id VARCHAR(50) NOT NULL,          -- 请求ID，格式：req_xxxxxxxxxxxxx
    api_key VARCHAR(100),                     -- 使用的API Key
    source_path VARCHAR(100),                 -- 来源路径标识
    method VARCHAR(10) NOT NULL,              -- HTTP方法
    path VARCHAR(500) NOT NULL,               -- 请求路径
    target_url VARCHAR(500),                  -- 目标URL
    status_code INTEGER,                      -- HTTP状态码
    request_time DATETIME NOT NULL,           -- 请求开始时间（中国时区 UTC+8）
    first_response_time DATETIME,             -- 最早响应时间（流式响应的首个数据块时间，中国时区 UTC+8）
    response_time DATETIME,                   -- 响应完成时间（中国时区 UTC+8）
    response_time_ms INTEGER,                 -- 响应时间（毫秒）
    request_size INTEGER DEFAULT 0,           -- 请求大小（字节）
    response_size INTEGER DEFAULT 0,          -- 响应大小（字节）
    user_agent VARCHAR(500),                  -- 用户代理
    ip_address VARCHAR(50),                   -- 客户端IP地址
    is_stream BOOLEAN DEFAULT FALSE,          -- 是否为流式响应
    stream_chunks INTEGER DEFAULT 0,          -- 流式响应块数
    error_message TEXT,                       -- 错误信息
    request_headers TEXT,                     -- 请求头（JSON字符串，可选记录）
    request_body TEXT,                        -- 请求体（JSON字符串，可选记录）
    response_headers TEXT,                    -- 响应头（JSON字符串，可选记录）
    response_body TEXT,                       -- 响应体（JSON字符串，可选记录）
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP -- 创建时间（中国时区 UTC+8）
);

-- 索引
CREATE INDEX idx_audit_logs_request_id ON audit_logs(request_id);
CREATE INDEX idx_audit_logs_api_key ON audit_logs(api_key);
CREATE INDEX idx_audit_logs_source_path ON audit_logs(source_path);
CREATE INDEX idx_audit_logs_request_time ON audit_logs(request_time);
CREATE INDEX idx_audit_logs_first_response_time ON audit_logs(first_response_time);
CREATE INDEX idx_audit_logs_is_stream ON audit_logs(is_stream);
CREATE INDEX idx_audit_logs_status_code ON audit_logs(status_code);
CREATE INDEX idx_audit_logs_created_at ON audit_logs(created_at);
```

### 3. proxy_routes - 通用代理路由配置表

```sql
CREATE TABLE proxy_routes (
    route_id VARCHAR(50) PRIMARY KEY,         -- 路由ID，格式：route_xxxxxxxxxxxxx
    route_name VARCHAR(100) NOT NULL,         -- 路由名称
    description TEXT,                         -- 路由描述
    
    -- 匹配规则
    match_path VARCHAR(500) NOT NULL,         -- 匹配路径模式，如：/v1/*
    match_method VARCHAR(20) DEFAULT 'ANY',   -- 匹配HTTP方法，如：POST,GET,ANY
    match_headers TEXT,                       -- 匹配请求头条件（JSON字符串）
    match_body_schema TEXT,                   -- 匹配请求体结构（JSON Schema字符串）
    
    -- 目标配置
    target_host VARCHAR(200) NOT NULL,        -- 目标主机，如：172.16.99.204:3398
    target_path VARCHAR(500) NOT NULL,        -- 目标路径，如：/v1/chat/completions
    target_protocol VARCHAR(10) DEFAULT 'http', -- 协议：http/https
    
    -- 转换规则
    strip_path_prefix BOOLEAN DEFAULT FALSE,  -- 是否剔除路径前缀
    add_headers TEXT,                         -- 新增请求头（JSON字符串）
    add_body_fields TEXT,                     -- 新增请求体字段（JSON字符串）
    remove_headers TEXT,                      -- 移除请求头列表（JSON数组字符串）
    
    -- 其他配置
    timeout INTEGER DEFAULT 30,              -- 超时时间（秒）
    retry_count INTEGER DEFAULT 0,           -- 重试次数
    is_active BOOLEAN DEFAULT TRUE,           -- 是否启用
    priority INTEGER DEFAULT 100,            -- 优先级（数字越小优先级越高）
    
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP, -- 创建时间（中国时区 UTC+8）
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP  -- 更新时间（中国时区 UTC+8）
);

-- 索引
CREATE INDEX idx_proxy_routes_match_path ON proxy_routes(match_path);
CREATE INDEX idx_proxy_routes_is_active ON proxy_routes(is_active);
CREATE INDEX idx_proxy_routes_priority ON proxy_routes(priority);
CREATE INDEX idx_proxy_routes_target_host ON proxy_routes(target_host);

-- 更新触发器
CREATE TRIGGER update_proxy_routes_updated_at 
    AFTER UPDATE ON proxy_routes
    FOR EACH ROW
    BEGIN
        UPDATE proxy_routes SET updated_at = CURRENT_TIMESTAMP WHERE route_id = NEW.route_id;
    END;
```



## 初始数据

### 示例代理路由配置

```sql
-- 示例：OpenAI风格的chat completions代理配置
INSERT OR IGNORE INTO proxy_routes (
    route_id, route_name, description,
    match_path, match_method, match_body_schema,
    target_host, target_path, target_protocol,
    add_headers, strip_path_prefix, 
    timeout, is_active, priority
) VALUES (
    'route_chat_v1', 'OpenAI Chat Completions v1', '代理OpenAI风格的聊天接口',
    '/v1/chat/completions', 'POST', '{"type":"object","properties":{"model":{"type":"string"},"messages":{"type":"array"}}}',
    '172.16.99.204:3398', '/v1/chat/completions', 'http',
    '{"Content-Type":"application/json","X-API-Source":"fastgate"}', false,
    30, true, 10
);

-- 示例：通用API代理配置
INSERT OR IGNORE INTO proxy_routes (
    route_id, route_name, description,
    match_path, match_method,
    target_host, target_path, target_protocol,
    strip_path_prefix, timeout, is_active, priority
) VALUES (
    'route_api_v2', 'API v2 代理', '代理所有v2 API请求',
    '/api/v2/*', 'ANY',
    '172.16.99.204:8080', '/api/v2', 'http',
    false, 30, true, 20
);
```

## 数据库配置

### 连接配置
- **数据库类型**: SQLite
- **数据库文件**: `app/data/fastgate.db`
- **连接池**: 使用SQLAlchemy连接池管理
- **事务管理**: 支持自动提交和回滚

### 性能优化
- **索引策略**: 为常用查询字段创建索引
- **触发器**: 自动更新时间戳字段
- **外键约束**: 暂未启用，保持简单性
- **数据压缩**: 审计日志可选择性存储详细信息

### 备份策略
- **定期备份**: 需要手动或定时任务备份SQLite文件
- **日志轮转**: 审计日志表需要定期清理过期数据
- **数据归档**: 可考虑将历史数据迁移到归档表

## 数据迁移
- 暂无数据迁移设计需求

### 版本管理
- **当前版本**: v0.2.0

### 升级路径 (v0.0.1 -> v0.2.0)
1. 已经删除数据库
2. 重新创建新版 初始化 数据库脚本。将init_databasse.py 放入 data目录下
3. 验证数据完整性
4. 更新应用配置 