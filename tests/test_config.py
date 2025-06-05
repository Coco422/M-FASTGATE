"""
配置系统单元测试 - v0.2.0
"""

import os
import pytest
import tempfile
import yaml
from pathlib import Path

# 添加项目根目录到Python路径
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.config import Config, load_config


class TestConfig:
    """配置系统测试类"""
    
    def setup_method(self):
        """每个测试方法前的设置"""
        # 清理环境变量
        env_vars_to_clear = [
            'DATABASE_URL', 'ADMIN_TOKEN', 'APP_DEBUG', 'APP_PORT'
        ]
        for var in env_vars_to_clear:
            if var in os.environ:
                del os.environ[var]
    
    def test_default_config_structure(self):
        """测试默认配置结构"""
        config = Config()
        
        # 验证配置结构
        assert hasattr(config, 'app')
        assert hasattr(config, 'database')
        assert hasattr(config, 'security')
        assert hasattr(config, 'logging')
        assert hasattr(config, 'rate_limiting')
        assert hasattr(config, 'proxy')
        
        # 验证默认值
        assert config.app['name'] == "M-FastGate"
        assert config.app['version'] == "0.2.0"
        assert config.app['port'] == 8514
        assert config.database['url'] == "sqlite:///./app/data/fastgate.db"
        assert config.security['key_prefix'] == "fg_"
    
    def test_config_yaml_loading(self):
        """测试config.yaml文件加载"""
        # 创建临时配置文件
        test_config = {
            'app': {
                'name': 'Test-FastGate',
                'version': '0.2.0-test',
                'port': 9999,
                'debug': True
            },
            'database': {
                'url': 'sqlite:///./test.db',
                'echo': True
            },
            'security': {
                'admin_token': 'test_token_123',
                'key_prefix': 'test_'
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(test_config, f)
            config_file = f.name
        
        try:
            config = load_config(config_file)
            
            # 验证加载的配置
            assert config.app['name'] == 'Test-FastGate'
            assert config.app['version'] == '0.2.0-test'
            assert config.app['port'] == 9999
            assert config.database['url'] == 'sqlite:///./test.db'
            assert config.security['admin_token'] == 'test_token_123'
            assert config.security['key_prefix'] == 'test_'
            
        finally:
            os.unlink(config_file)
    
    def test_environment_variable_override(self):
        """测试环境变量覆盖"""
        # 设置环境变量
        os.environ['DATABASE_URL'] = 'sqlite:///./env_test.db'
        os.environ['ADMIN_TOKEN'] = 'env_token_456'
        os.environ['APP_DEBUG'] = 'false'
        os.environ['APP_PORT'] = '7777'
        
        config = Config()
        config.apply_env_overrides()
        
        # 验证环境变量覆盖
        assert config.database['url'] == 'sqlite:///./env_test.db'
        assert config.security['admin_token'] == 'env_token_456'
        assert config.app['debug'] == False
        assert config.app['port'] == 7777
    
    def test_config_validation(self):
        """测试配置验证"""
        config = Config()
        
        # 测试有效配置
        assert config.validate()
        
        # 测试无效配置
        config.config['app']['port'] = -1  # 无效端口
        assert not config.validate()
        
        config.config['app']['port'] = 8514  # 恢复有效端口
        config.config['database']['url'] = ""  # 空数据库URL
        assert not config.validate()
    
    def test_proxy_config_structure(self):
        """测试代理配置结构"""
        config = Config()
        
        assert 'proxy' in config.config
        proxy_config = config.config['proxy']
        
        # 验证代理配置字段
        assert 'timeout' in proxy_config
        assert 'max_retries' in proxy_config
        assert 'enable_streaming' in proxy_config
        assert 'strip_headers' in proxy_config
        assert 'async_audit' in proxy_config
        
        # 验证默认值
        assert proxy_config['timeout'] == 30
        assert proxy_config['max_retries'] == 3
        assert proxy_config['enable_streaming'] == True
        assert isinstance(proxy_config['strip_headers'], list)
    
    def test_missing_config_file_fallback(self):
        """测试配置文件不存在时的回退机制"""
        non_existent_file = '/non/existent/config.yaml'
        
        # 应该回退到默认配置
        config = load_config(non_existent_file)
        
        # 验证回退到默认配置
        assert config.app['name'] == "M-FastGate"
        assert config.app['version'] == "0.2.0"
    
    def test_partial_config_file(self):
        """测试部分配置文件（只包含部分配置项）"""
        partial_config = {
            'app': {
                'port': 8888
            },
            'security': {
                'admin_token': 'partial_token'
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(partial_config, f)
            config_file = f.name
        
        try:
            config = load_config(config_file)
            
            # 验证部分覆盖的配置
            assert config.app['port'] == 8888  # 被覆盖
            assert config.app['name'] == "M-FastGate"  # 保持默认值
            assert config.security['admin_token'] == 'partial_token'  # 被覆盖
            assert config.security['key_prefix'] == "fg_"  # 保持默认值
            
        finally:
            os.unlink(config_file)


class TestConfigIntegration:
    """配置系统集成测试"""
    
    def test_config_with_database_init(self):
        """测试配置与数据库初始化的集成"""
        # 这个测试确保config/config.yaml中的database.url能被数据库初始化器正确使用
        config = Config()
        db_url = config.database['url']
        
        # 验证数据库URL格式
        assert db_url.startswith('sqlite:///')
        assert 'fastgate.db' in db_url
        
        # 验证路径是相对于项目根目录
        assert './app/data/' in db_url
    
    def test_config_consistency_with_design(self):
        """测试配置与设计文档的一致性"""
        config = Config()
        
        # 验证与design-v0.2.0.md中描述的配置结构一致
        expected_sections = ['app', 'database', 'security', 'logging', 'rate_limiting', 'proxy']
        for section in expected_sections:
            assert section in config.config, f"Missing config section: {section}"
        
        # 验证关键配置项
        assert config.app['version'] == "0.2.0"
        assert config.app['port'] == 8514
        assert config.database['echo'] == False
        assert config.proxy['enable_streaming'] == True


# 测试辅助函数
def test_load_config_function():
    """测试load_config函数"""
    # 测试默认配置加载
    config = load_config()
    assert isinstance(config, Config)
    
    # 测试指定文件加载
    config = load_config('config/config.yaml')
    assert isinstance(config, Config) 