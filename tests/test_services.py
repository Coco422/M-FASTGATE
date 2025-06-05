"""
核心服务单元测试 - v0.2.0
测试驱动开发：proxy_engine, route_matcher, audit_service, proxy_route_manager
"""

import os
import sys
import json
import pytest
import asyncio
import httpx
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timezone, timedelta

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.config import settings
from app.models.proxy_route import ProxyRouteDB, ProxyRouteCreate, ProxyRouteUpdate
from app.models.audit_log import AuditLogDB, AuditLogCreate


class TestProxyEngine:
    """代理引擎测试类"""
    
    @pytest.fixture
    def mock_route_config(self):
        """模拟代理路由配置"""
        return {
            "route_id": "route_test_123",
            "route_name": "Test Route",
            "match_path": "/v1/test",
            "match_method": "POST",
            "target_host": "api.example.com",
            "target_path": "/v1/chat/completions",
            "target_protocol": "https",
            "timeout": 30,
            "retry_count": 3,
            "add_headers": {"X-Source": "fastgate"},
            "remove_headers": ["user-agent"]
        }
    
    @pytest.mark.asyncio
    async def test_proxy_engine_init(self):
        """测试代理引擎初始化"""
        from app.services.proxy_engine import ProxyEngine
        
        engine = ProxyEngine()
        assert engine is not None
        assert hasattr(engine, 'client')
        assert hasattr(engine, 'forward_request')
        assert hasattr(engine, 'handle_stream_response')
        
        # 清理
        await engine.close()
    
    @pytest.mark.asyncio
    async def test_forward_request_success(self, mock_route_config):
        """测试请求转发成功"""
        from app.services.proxy_engine import ProxyEngine
        
        engine = ProxyEngine()
        
        # 模拟HTTP客户端响应
        with patch.object(engine, 'client') as mock_client:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.headers = {"content-type": "application/json"}
            mock_response.content = b'{"result": "success"}'
            mock_response.aiter_bytes = AsyncMock(return_value=[b'{"result": "success"}'])
            
            mock_client.request = AsyncMock(return_value=mock_response)
            
            # 测试请求
            response = await engine.forward_request(
                route_config=mock_route_config,
                method="POST",
                url="https://api.example.com/v1/chat/completions",
                headers={"Content-Type": "application/json"},
                json={"model": "gpt-3.5-turbo", "messages": []}
            )
            
            assert response.status_code == 200
            mock_client.request.assert_called_once()
        
        await engine.close()
    
    @pytest.mark.asyncio
    async def test_forward_request_with_retry(self, mock_route_config):
        """测试请求重试机制"""
        from app.services.proxy_engine import ProxyEngine
        
        engine = ProxyEngine()
        
        with patch.object(engine, 'client') as mock_client:
            # 第一次失败，第二次成功
            mock_success_response = Mock()
            mock_success_response.status_code = 200
            mock_success_response.headers = {}
            mock_success_response.content = b'{"success": true}'
            
            mock_client.request = AsyncMock(side_effect=[
                httpx.ConnectError("Connection failed"),
                mock_success_response
            ])
            
            response = await engine.forward_request(
                route_config=mock_route_config,
                method="POST",
                url="https://api.example.com/v1/test",
                headers={"Content-Type": "application/json"},
                json={"test": "data"}
            )
            
            # 验证重试了一次
            assert mock_client.request.call_count == 2
            assert response.status_code == 200
        
        await engine.close()
    
    @pytest.mark.asyncio
    async def test_handle_stream_response(self):
        """测试流式响应处理"""
        from app.services.proxy_engine import ProxyEngine
        
        engine = ProxyEngine()
        
        # 模拟流式响应
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "text/event-stream"}
        mock_response.aclose = AsyncMock()
        
        async def mock_aiter_bytes(chunk_size=8192):
            chunks = [b'data: {"chunk": 1}\n\n', b'data: {"chunk": 2}\n\n', b'data: [DONE]\n\n']
            for chunk in chunks:
                yield chunk
        
        mock_response.aiter_bytes = mock_aiter_bytes
        
        stream_response = await engine.handle_stream_response(mock_response)
        
        # 验证流式响应包装器
        assert hasattr(stream_response, 'status_code')
        assert stream_response.status_code == 200
        
        await engine.close()


class TestRouteMatcher:
    """路由匹配引擎测试类"""
    
    @pytest.fixture
    def sample_routes(self):
        """示例路由配置"""
        return [
            {
                "route_id": "route_chat",
                "match_path": "/v1/chat/completions",
                "match_method": "POST",
                "match_headers": {"content-type": "application/json"},
                "priority": 10,
                "is_active": True
            },
            {
                "route_id": "route_api_v1",
                "match_path": "/v1/*",
                "match_method": "ANY",
                "priority": 20,
                "is_active": True
            },
            {
                "route_id": "route_specific",
                "match_path": "/v1/models",
                "match_method": "GET",
                "priority": 5,
                "is_active": True
            }
        ]
    
    def test_route_matcher_init(self):
        """测试路由匹配器初始化"""
        from app.services.route_matcher import RouteMatcher
        
        matcher = RouteMatcher()
        assert matcher is not None
        assert hasattr(matcher, 'find_matching_route')
        assert hasattr(matcher, 'match_path')
        assert hasattr(matcher, 'match_method')
    
    def test_path_matching(self, sample_routes):
        """测试路径匹配"""
        from app.services.route_matcher import RouteMatcher
        
        matcher = RouteMatcher()
        
        # 精确匹配
        result = matcher.match_path("/v1/chat/completions", "/v1/chat/completions")
        assert result is True
        
        # 通配符匹配
        result = matcher.match_path("/v1/models", "/v1/*")
        assert result is True
        
        result = matcher.match_path("/v2/models", "/v1/*")
        assert result is False
    
    def test_method_matching(self):
        """测试HTTP方法匹配"""
        from app.services.route_matcher import RouteMatcher
        
        matcher = RouteMatcher()
        
        # 精确匹配
        assert matcher.match_method("POST", "POST") is True
        assert matcher.match_method("GET", "POST") is False
        
        # ANY匹配
        assert matcher.match_method("POST", "ANY") is True
        assert matcher.match_method("GET", "ANY") is True
        
        # 多方法匹配
        assert matcher.match_method("POST", "POST,GET") is True
        assert matcher.match_method("DELETE", "POST,GET") is False
    
    def test_find_matching_route(self, sample_routes):
        """测试查找匹配的路由"""
        from app.services.route_matcher import RouteMatcher
        
        matcher = RouteMatcher()
        
        # 测试精确匹配（最高优先级）
        request = {
            "path": "/v1/models",
            "method": "GET",
            "headers": {}
        }
        
        route = matcher.find_matching_route(request, sample_routes)
        assert route is not None
        assert route["route_id"] == "route_specific"  # 优先级最高
        
        # 测试通配符匹配
        request = {
            "path": "/v1/embeddings",
            "method": "POST",
            "headers": {}
        }
        
        route = matcher.find_matching_route(request, sample_routes)
        assert route is not None
        assert route["route_id"] == "route_api_v1"
    
    def test_request_headers_matching(self):
        """测试请求头匹配"""
        from app.services.route_matcher import RouteMatcher
        
        matcher = RouteMatcher()
        
        route_headers = {"content-type": "application/json"}
        request_headers = {"content-type": "application/json", "authorization": "Bearer token"}
        
        result = matcher.match_headers(request_headers, route_headers)
        assert result is True
        
        request_headers = {"content-type": "text/plain"}
        result = matcher.match_headers(request_headers, route_headers)
        assert result is False


# 暂时简化其他测试类，先专注于核心功能
class TestServicesBasic:
    """基础服务测试"""
    
    def test_proxy_engine_import(self):
        """测试代理引擎可以正常导入"""
        from app.services.proxy_engine import ProxyEngine
        assert ProxyEngine is not None
    
    def test_route_matcher_import(self):
        """测试路由匹配器可以正常导入"""
        from app.services.route_matcher import RouteMatcher
        assert RouteMatcher is not None 