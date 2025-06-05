-- Phase 2.4: 添加模型路由功能相关表
-- 执行时间: 2024-01-XX

-- 模型路由配置表
CREATE TABLE IF NOT EXISTS model_routes (
    id VARCHAR(50) PRIMARY KEY,
    model_name VARCHAR(100) NOT NULL UNIQUE,
    endpoint_type VARCHAR(20) NOT NULL,  -- 'chat' 或 'embedding'
    proxy_path VARCHAR(500) NOT NULL,    -- '/**' 或 '/embed'
    parameters TEXT,  -- 使用TEXT而不是JSON (SQLite兼容)
    health_check_path VARCHAR(500) DEFAULT '/health',
    timeout INTEGER DEFAULT 30,
    max_retries INTEGER DEFAULT 3,
    is_active BOOLEAN DEFAULT TRUE,
    health_status VARCHAR(20) DEFAULT 'unknown',
    last_health_check TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
    date VARCHAR(10) NOT NULL,  -- YYYY-MM-DD
    hour INTEGER NOT NULL,      -- 0-23
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 创建复合唯一索引（替代UNIQUE约束）
CREATE UNIQUE INDEX IF NOT EXISTS idx_model_usage_unique ON model_usage_stats(model_name, api_key, source_path, date, hour);

-- 索引
CREATE INDEX IF NOT EXISTS idx_model_routes_model_name ON model_routes(model_name);
CREATE INDEX IF NOT EXISTS idx_model_routes_active ON model_routes(is_active);
CREATE INDEX IF NOT EXISTS idx_model_routes_health ON model_routes(health_status);
CREATE INDEX IF NOT EXISTS idx_model_routes_type ON model_routes(endpoint_type);

CREATE INDEX IF NOT EXISTS idx_model_usage_stats_model_date ON model_usage_stats(model_name, date);
CREATE INDEX IF NOT EXISTS idx_model_usage_stats_api_key ON model_usage_stats(api_key);
CREATE INDEX IF NOT EXISTS idx_model_usage_stats_hour ON model_usage_stats(date, hour);

-- 插入初始模型路由配置
INSERT OR IGNORE INTO model_routes (id, model_name, endpoint_type, proxy_path, parameters, is_active) VALUES
('route_deepseekr1', 'DeepSeekR1', 'chat', '/**', '{"max_concurrency": 100, "context_length": "32K/8K", "recommended_temperature": 0.6, "recommended_top_p": 0.95}', 1),
('route_qwq32b', 'QwQ-32B', 'chat', '/**', '{"max_concurrency": 100, "context_length": "120K/8K"}', 1),
('route_qwen25_32b', 'Qwen2.5-32B-Instruct', 'chat', '/**', '{"max_concurrency": 100, "context_length": "120K/8K"}', 1),
('route_bge_large_zh', 'bge-large-zh-v1.5', 'embedding', '/embed', '{"max_input_tokens": 512, "output_dimensions": 1024, "embedding_type": "text"}', 1);

-- 添加触发器更新 updated_at 字段
CREATE TRIGGER IF NOT EXISTS update_model_routes_updated_at 
    AFTER UPDATE ON model_routes
    FOR EACH ROW
    BEGIN
        UPDATE model_routes SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
    END;

CREATE TRIGGER IF NOT EXISTS update_model_usage_stats_updated_at 
    AFTER UPDATE ON model_usage_stats
    FOR EACH ROW
    BEGIN
        UPDATE model_usage_stats SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
    END; 