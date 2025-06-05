"""
配置管理模块
"""

import os
from typing import List, Dict, Any, Optional
from pydantic import Field
from pydantic_settings import BaseSettings
import yaml


class DatabaseConfig(BaseSettings):
    """数据库配置"""
    url: str = "sqlite:///./fastgate.db"
    echo: bool = True


class LoggingConfig(BaseSettings):
    """日志配置"""
    level: str = "INFO"
    format: str = "json"
    file: str = "logs/fastgate.log"


class SecurityConfig(BaseSettings):
    """安全配置"""
    admin_token: str = "admin_secret_token"
    key_prefix: str = "fg_"
    default_expiry_days: int = 365


class RateLimitingConfig(BaseSettings):
    """限流配置"""
    enabled: bool = True
    default_requests_per_minute: int = 100


class CloudProxyConfig(BaseSettings):
    """云天代理服务配置"""
    host: str = "10.101.32.14"
    port: int = 34094
    base_path: str = "/openapi/proxy"


class ModelRoutingConfig(BaseSettings):
    """模型路由配置"""
    enabled: bool = True
    app_key: str = "1_C2D6F4B1183D592E04BA216D71A84F17"
    system_source: str = "智能客服系统"
    config_path: str = "config/model_routes.yaml"


class APIGatewayConfig(BaseSettings):
    """API网关专门配置"""
    # 后端服务配置
    backend_url: str = "http://172.16.99.32:1030"
    backend_path: str = "/miniai/v2/chat/completions"
    real_api_key: str = "your_real_api_key_here"
    
    # 请求配置
    timeout: int = 30
    max_retries: int = 3
    
    # 参数清洗配置
    strip_headers: List[str] = [
        "host", "x-api-key", "authorization", "x-forwarded-for", 
        "x-real-ip", "x-source-path", "user-agent"
    ]
    strip_body_fields: List[str] = []  # 需要从请求体中移除的字段
    
    # 异步审计配置
    async_audit: bool = True
    audit_full_request: bool = True
    audit_full_response: bool = True


class AppConfig(BaseSettings):
    """应用主配置"""
    name: str = "M-FastGate"
    version: str = "0.0.1"
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 8514


class RouteTarget(BaseSettings):
    """路由目标配置"""
    url: str
    timeout: int = 30
    weight: int = 100
    
    model_config = {"extra": "ignore"}


class RouteConfig(BaseSettings):
    """单个路由配置"""
    name: str
    path_prefix: str
    targets: List[RouteTarget]
    auth_required: bool = True
    rate_limit: Optional[int] = None
    
    model_config = {"extra": "ignore"}


class Settings(BaseSettings):
    """全局配置类"""
    app: AppConfig = AppConfig()
    database: DatabaseConfig = DatabaseConfig()
    logging: LoggingConfig = LoggingConfig()
    security: SecurityConfig = SecurityConfig()
    rate_limiting: RateLimitingConfig = RateLimitingConfig()
    api_gateway: APIGatewayConfig = APIGatewayConfig()
    cloud_proxy: CloudProxyConfig = CloudProxyConfig()
    model_routing: ModelRoutingConfig = ModelRoutingConfig()
    
    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
        "extra": "ignore"  # 忽略额外的环境变量
    }


def load_config(config_file: str = None) -> Settings:
    """
    加载配置文件
    
    Args:
        config_file: 配置文件路径，默认根据环境变量确定
    
    Returns:
        Settings: 配置对象
    """
    if config_file is None:
        env = os.getenv("ENVIRONMENT", "development")
        config_file = f"config/{env}.yaml"
    
    # 检查配置文件是否存在
    if os.path.exists(config_file):
        with open(config_file, 'r', encoding='utf-8') as f:
            config_data = yaml.safe_load(f)
        
        # 创建配置对象
        settings = Settings()
        
        # 更新配置
        if 'app' in config_data:
            settings.app = AppConfig(**config_data['app'])
        if 'database' in config_data:
            settings.database = DatabaseConfig(**config_data['database'])
        if 'logging' in config_data:
            settings.logging = LoggingConfig(**config_data['logging'])
        if 'security' in config_data:
            settings.security = SecurityConfig(**config_data['security'])
        if 'rate_limiting' in config_data:
            settings.rate_limiting = RateLimitingConfig(**config_data['rate_limiting'])
        if 'api_gateway' in config_data:
            settings.api_gateway = APIGatewayConfig(**config_data['api_gateway'])
        if 'cloud_proxy' in config_data:
            settings.cloud_proxy = CloudProxyConfig(**config_data['cloud_proxy'])
        if 'model_routing' in config_data:
            settings.model_routing = ModelRoutingConfig(**config_data['model_routing'])
        
        return settings
    else:
        # 如果配置文件不存在，使用默认配置
        return Settings()


def load_routes_config(routes_file: str = "config/routes.yaml") -> List[RouteConfig]:
    """
    加载路由配置
    
    Args:
        routes_file: 路由配置文件路径
    
    Returns:
        List[RouteConfig]: 路由配置列表
    """
    if not os.path.exists(routes_file):
        return []
    
    with open(routes_file, 'r', encoding='utf-8') as f:
        routes_data = yaml.safe_load(f)
    
    routes = []
    for route_data in routes_data.get('routes', []):
        # 处理targets
        targets = []
        for target_data in route_data.get('targets', []):
            targets.append(RouteTarget(**target_data))
        
        route_data['targets'] = targets
        routes.append(RouteConfig(**route_data))
    
    return routes


# 全局配置实例
settings = load_config()
routes_config = load_routes_config()