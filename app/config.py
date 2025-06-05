"""
配置管理模块 - v0.2.0
简化的统一配置系统
"""

import os
import yaml
from typing import Dict, Any, Optional
from pathlib import Path


class Config:
    """统一配置类"""
    
    def __init__(self, config_file: Optional[str] = None):
        """
        初始化配置
        
        Args:
            config_file: 配置文件路径，默认为config/config.yaml
        """
        self.config_file = config_file or "config/config.yaml"
        self.config = self._load_default_config()
        self._load_config_file()
        self.apply_env_overrides()
    
    def _load_default_config(self) -> Dict[str, Any]:
        """加载默认配置"""
        return {
            "app": {
                "name": "M-FastGate",
                "version": "0.2.0",
                "host": "0.0.0.0",
                "port": 8514,
                "debug": True
            },
            "database": {
                "url": "sqlite:///./app/data/fastgate.db",
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
    
    def _load_config_file(self):
        """加载配置文件"""
        if not os.path.exists(self.config_file):
            print(f"⚠️  配置文件不存在: {self.config_file}，使用默认配置")
            return
        
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                file_config = yaml.safe_load(f)
            
            if file_config:
                # 深度合并配置
                self._deep_merge(self.config, file_config)
                print(f"✅ 成功加载配置文件: {self.config_file}")
            
        except Exception as e:
            print(f"❌ 加载配置文件失败: {e}，使用默认配置")
    
    def _deep_merge(self, base_dict: Dict, update_dict: Dict):
        """深度合并字典"""
        for key, value in update_dict.items():
            if key in base_dict and isinstance(base_dict[key], dict) and isinstance(value, dict):
                self._deep_merge(base_dict[key], value)
            else:
                base_dict[key] = value
    
    def apply_env_overrides(self):
        """应用环境变量覆盖"""
        # 数据库配置
        if os.getenv("DATABASE_URL"):
            self.config["database"]["url"] = os.getenv("DATABASE_URL")
        
        # 安全配置
        if os.getenv("ADMIN_TOKEN"):
            self.config["security"]["admin_token"] = os.getenv("ADMIN_TOKEN")
        
        # 应用配置
        if os.getenv("APP_DEBUG"):
            self.config["app"]["debug"] = os.getenv("APP_DEBUG").lower() == 'true'
        
        if os.getenv("APP_PORT"):
            try:
                self.config["app"]["port"] = int(os.getenv("APP_PORT"))
            except ValueError:
                print(f"⚠️  无效的APP_PORT环境变量: {os.getenv('APP_PORT')}")
        
        if os.getenv("APP_HOST"):
            self.config["app"]["host"] = os.getenv("APP_HOST")
        
        # 日志配置
        if os.getenv("LOG_LEVEL"):
            self.config["logging"]["level"] = os.getenv("LOG_LEVEL")
        
        if os.getenv("LOG_FILE"):
            self.config["logging"]["file"] = os.getenv("LOG_FILE")
    
    def validate(self) -> bool:
        """验证配置有效性"""
        try:
            # 验证应用配置
            if not isinstance(self.config["app"]["port"], int) or self.config["app"]["port"] <= 0:
                print("❌ 无效的应用端口配置")
                return False
            
            # 验证数据库配置
            if not self.config["database"]["url"] or not isinstance(self.config["database"]["url"], str):
                print("❌ 无效的数据库URL配置")
                return False
            
            # 验证安全配置
            if not self.config["security"]["admin_token"]:
                print("❌ 缺少管理员令牌配置")
                return False
            
            # 验证代理配置
            proxy_config = self.config["proxy"]
            if not isinstance(proxy_config["timeout"], int) or proxy_config["timeout"] <= 0:
                print("❌ 无效的代理超时配置")
                return False
            
            if not isinstance(proxy_config["max_retries"], int) or proxy_config["max_retries"] < 0:
                print("❌ 无效的代理重试次数配置")
                return False
            
            return True
            
        except KeyError as e:
            print(f"❌ 缺少必要的配置项: {e}")
            return False
        except Exception as e:
            print(f"❌ 配置验证失败: {e}")
            return False
    
    @property
    def app(self) -> Dict[str, Any]:
        """获取应用配置"""
        return self.config["app"]
    
    @property
    def database(self) -> Dict[str, Any]:
        """获取数据库配置"""
        return self.config["database"]
    
    @property
    def security(self) -> Dict[str, Any]:
        """获取安全配置"""
        return self.config["security"]
    
    @property
    def logging(self) -> Dict[str, Any]:
        """获取日志配置"""
        return self.config["logging"]
    
    @property
    def rate_limiting(self) -> Dict[str, Any]:
        """获取限流配置"""
        return self.config["rate_limiting"]
    
    @property
    def proxy(self) -> Dict[str, Any]:
        """获取代理配置"""
        return self.config["proxy"]
    
    def get(self, key: str, default: Any = None) -> Any:
        """获取配置项"""
        keys = key.split('.')
        value = self.config
        
        try:
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            return default
    
    def set(self, key: str, value: Any):
        """设置配置项"""
        keys = key.split('.')
        target = self.config
        
        for k in keys[:-1]:
            if k not in target:
                target[k] = {}
            target = target[k]
        
        target[keys[-1]] = value
    
    def reload(self):
        """重新加载配置"""
        self.config = self._load_default_config()
        self._load_config_file()
        self.apply_env_overrides()


def load_config(config_file: Optional[str] = None) -> Config:
    """
    加载配置
    
    Args:
        config_file: 配置文件路径
    
    Returns:
        Config: 配置对象
    """
    return Config(config_file)


# 全局配置实例
settings = load_config()


# 向后兼容的配置访问（用于现有代码）
class DatabaseConfig:
    """数据库配置（向后兼容）"""
    @property
    def url(self) -> str:
        return settings.database['url']
    
    @property
    def echo(self) -> bool:
        return settings.database['echo']


class SecurityConfig:
    """安全配置（向后兼容）"""
    @property
    def admin_token(self) -> str:
        return settings.security['admin_token']
    
    @property
    def key_prefix(self) -> str:
        return settings.security['key_prefix']
    
    @property
    def default_expiry_days(self) -> int:
        return settings.security['default_expiry_days']


class LoggingConfig:
    """日志配置（向后兼容）"""
    @property
    def level(self) -> str:
        return settings.logging['level']
    
    @property
    def format(self) -> str:
        return settings.logging['format']
    
    @property
    def file(self) -> str:
        return settings.logging['file']


# 向后兼容的全局配置对象
class Settings:
    """全局配置类（向后兼容）"""
    def __init__(self):
        self.database = DatabaseConfig()
        self.security = SecurityConfig()
        self.logging = LoggingConfig()


# 导出向后兼容的配置实例
settings_compat = Settings()