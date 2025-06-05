#!/usr/bin/env python3
"""
M-FastGate v0.2.0 管理API测试
测试所有管理接口的功能，包括API Key管理、代理路由管理、审计日志查询等
"""

import pytest
import json
from fastapi.testclient import TestClient
from datetime import datetime, timedelta

from app.main import app
from app.database import get_db, create_tables
from app.models.api_key import APIKeyDB
from app.models.proxy_route import ProxyRouteDB
from app.models.audit_log import AuditLogDB
from app.config import settings

# 测试客户端
client = TestClient(app)

# 测试用的管理员token
ADMIN_TOKEN = settings.security['admin_token']
ADMIN_HEADERS = {"Authorization": f"Bearer {ADMIN_TOKEN}"}


@pytest.fixture(scope="function")
def test_db():
    """测试数据库fixture"""
    create_tables()
    db = next(get_db())
    yield db
    # 清理测试数据
    db.query(APIKeyDB).delete()
    db.query(ProxyRouteDB).delete()
    db.query(AuditLogDB).delete()
    db.commit()
    db.close()


@pytest.fixture
def sample_api_key(test_db):
    """创建示例API Key"""
    api_key = APIKeyDB(
        key_id="fg_test123456",
        key_value="fg_test_key_value_12345",
        source_path="test-app",
        permissions=["chat.completions"],
        expires_at=datetime.utcnow() + timedelta(days=30),
        is_active=True,
        rate_limit=1000
    )
    test_db.add(api_key)
    test_db.commit()
    test_db.refresh(api_key)
    return api_key


@pytest.fixture
def sample_proxy_route(test_db):
    """创建示例代理路由"""
    route = ProxyRouteDB(
        route_id="test-route",
        route_name="Test Route",
        description="测试路由",
        match_path="/test/*",
        match_method="POST",
        target_host="localhost:8000",
        target_path="/api/test",
        target_protocol="http",
        add_headers='{"Authorization": "Bearer test-token"}',
        remove_headers='["host"]',
        is_active=True,
        priority=100
    )
    test_db.add(route)
    test_db.commit()
    test_db.refresh(route)
    return route


class TestAPIKeyManagement:
    """API Key管理测试"""
    
    def test_create_api_key(self, test_db):
        """测试创建API Key"""
        data = {
            "source_path": "test-create-app",
            "permissions": ["chat.completions", "models.list"],
            "expires_days": 90,
            "rate_limit": 2000
        }
        
        response = client.post("/admin/keys", json=data, headers=ADMIN_HEADERS)
        
        assert response.status_code == 200
        result = response.json()
        
        assert result["source_path"] == "test-create-app"
        assert result["permissions"] == ["chat.completions", "models.list"]
        assert result["rate_limit"] == 2000
        assert result["is_active"] is True
        assert "key_id" in result
        assert "key_value" in result
        assert result["key_value"].startswith("fg_")
    
    def test_get_api_keys(self, test_db, sample_api_key):
        """测试获取API Key列表"""
        response = client.get("/admin/keys", headers=ADMIN_HEADERS)
        
        assert response.status_code == 200
        result = response.json()
        
        assert isinstance(result, list)
        assert len(result) >= 1
        
        key = next((k for k in result if k["key_id"] == sample_api_key.key_id), None)
        assert key is not None
        assert key["source_path"] == "test-app"
    
    def test_get_api_key_by_id(self, test_db, sample_api_key):
        """测试根据ID获取API Key"""
        response = client.get(f"/admin/keys/{sample_api_key.key_id}", headers=ADMIN_HEADERS)
        
        assert response.status_code == 200
        result = response.json()
        
        assert result["key_id"] == sample_api_key.key_id
        assert result["source_path"] == "test-app"
    
    def test_update_api_key(self, test_db, sample_api_key):
        """测试更新API Key"""
        data = {
            "source_path": "updated-test-app",
            "rate_limit": 3000,
            "is_active": False
        }
        
        response = client.put(f"/admin/keys/{sample_api_key.key_id}", json=data, headers=ADMIN_HEADERS)
        
        assert response.status_code == 200
        result = response.json()
        
        assert result["source_path"] == "updated-test-app"
        assert result["rate_limit"] == 3000
        assert result["is_active"] is False
    
    def test_delete_api_key(self, test_db, sample_api_key):
        """测试删除API Key"""
        response = client.delete(f"/admin/keys/{sample_api_key.key_id}", headers=ADMIN_HEADERS)
        
        assert response.status_code == 200
        
        # 验证已删除
        response = client.get(f"/admin/keys/{sample_api_key.key_id}", headers=ADMIN_HEADERS)
        assert response.status_code == 404
    
    def test_api_key_filters(self, test_db, sample_api_key):
        """测试API Key过滤功能"""
        # 按source_path过滤
        response = client.get("/admin/keys?source_path=test-app", headers=ADMIN_HEADERS)
        assert response.status_code == 200
        result = response.json()
        assert len(result) >= 1
        
        # 按is_active过滤
        response = client.get("/admin/keys?is_active=true", headers=ADMIN_HEADERS)
        assert response.status_code == 200
        result = response.json()
        assert len(result) >= 1


class TestProxyRouteManagement:
    """代理路由管理测试"""
    
    def test_create_proxy_route(self, test_db):
        """测试创建代理路由"""
        data = {
            "route_name": "Test API Route",
            "description": "测试API路由",
            "match_path": "/api/v1/*",
            "match_method": "POST",
            "match_body_schema": '{"model": "test-model"}',
            "target_host": "example.com:443",
            "target_path": "/api/v1/test",
            "target_protocol": "https",
            "add_headers": '{"Authorization": "Bearer secret-key", "X-Source": "gateway"}',
            "remove_headers": '["host", "user-agent"]',
            "timeout": 60,
            "retry_count": 2,
            "priority": 50,
            "is_active": True
        }
        
        response = client.post("/admin/routes", json=data, headers=ADMIN_HEADERS)
        
        assert response.status_code == 200
        result = response.json()
        
        assert result["route_name"] == "Test API Route"
        assert result["match_path"] == "/api/v1/*"
        assert result["target_host"] == "example.com:443"
        assert result["priority"] == 50
        assert "route_id" in result
    
    def test_get_proxy_routes(self, test_db, sample_proxy_route):
        """测试获取代理路由列表"""
        response = client.get("/admin/routes", headers=ADMIN_HEADERS)
        
        assert response.status_code == 200
        result = response.json()
        
        assert isinstance(result, list)
        assert len(result) >= 1
        
        route = next((r for r in result if r["route_id"] == sample_proxy_route.route_id), None)
        assert route is not None
        assert route["route_name"] == "Test Route"
    
    def test_get_proxy_route_by_id(self, test_db, sample_proxy_route):
        """测试根据ID获取代理路由"""
        response = client.get(f"/admin/routes/{sample_proxy_route.route_id}", headers=ADMIN_HEADERS)
        
        assert response.status_code == 200
        result = response.json()
        
        assert result["route_id"] == sample_proxy_route.route_id
        assert result["route_name"] == "Test Route"
    
    def test_update_proxy_route(self, test_db, sample_proxy_route):
        """测试更新代理路由"""
        data = {
            "route_name": "Updated Test Route",
            "priority": 200,
            "is_active": False
        }
        
        response = client.put(f"/admin/routes/{sample_proxy_route.route_id}", json=data, headers=ADMIN_HEADERS)
        
        assert response.status_code == 200
        result = response.json()
        
        assert result["route_name"] == "Updated Test Route"
        assert result["priority"] == 200
        assert result["is_active"] is False
    
    def test_toggle_route_status(self, test_db, sample_proxy_route):
        """测试切换路由状态"""
        data = {"is_active": False}
        
        response = client.post(f"/admin/routes/{sample_proxy_route.route_id}/toggle", json=data, headers=ADMIN_HEADERS)
        
        assert response.status_code == 200
        
        # 验证状态已更改
        response = client.get(f"/admin/routes/{sample_proxy_route.route_id}", headers=ADMIN_HEADERS)
        result = response.json()
        assert result["is_active"] is False
    
    def test_route_test_endpoint(self, test_db, sample_proxy_route):
        """测试路由测试端点"""
        data = {
            "test_method": "POST",
            "test_headers": {"Content-Type": "application/json"},
            "test_body": {"test": "data"},
            "timeout": 5
        }
        
        response = client.post(f"/admin/routes/{sample_proxy_route.route_id}/test", json=data, headers=ADMIN_HEADERS)
        
        # 由于是测试环境，后端服务可能不可用，但应该返回测试结果结构
        assert response.status_code in [200, 502]  # 200成功或502后端不可用
        
        if response.status_code == 200:
            result = response.json()
            assert "success" in result
            assert "matched" in result
            assert "target_url" in result
    
    def test_delete_proxy_route(self, test_db, sample_proxy_route):
        """测试删除代理路由"""
        response = client.delete(f"/admin/routes/{sample_proxy_route.route_id}", headers=ADMIN_HEADERS)
        
        assert response.status_code == 200
        
        # 验证已删除
        response = client.get(f"/admin/routes/{sample_proxy_route.route_id}", headers=ADMIN_HEADERS)
        assert response.status_code == 404


class TestAuditLogQuery:
    """审计日志查询测试"""
    
    @pytest.fixture
    def sample_audit_log(self, test_db):
        """创建示例审计日志"""
        log = AuditLogDB(
            id="log_test_12345",
            request_id="req_test_12345",
            api_key="fg_test_key",
            source_path="test-app",
            method="POST",
            path="/v1/chat/completions",
            target_url="http://localhost:8000/api/test",
            status_code=200,
            request_time=datetime.utcnow(),
            first_response_time=datetime.utcnow(),
            response_time=datetime.utcnow(),
            response_time_ms=150,
            request_size=256,
            response_size=1024,
            user_agent="test-client",
            ip_address="127.0.0.1",
            is_stream=False
        )
        test_db.add(log)
        test_db.commit()
        test_db.refresh(log)
        return log
    
    def test_get_audit_logs(self, test_db, sample_audit_log):
        """测试获取审计日志"""
        response = client.get("/admin/logs", headers=ADMIN_HEADERS)
        
        assert response.status_code == 200
        result = response.json()
        
        assert isinstance(result, list)
        assert len(result) >= 1
        
        log = next((l for l in result if l["id"] == sample_audit_log.id), None)
        assert log is not None
        assert log["method"] == "POST"
        assert log["path"] == "/v1/chat/completions"
    
    def test_get_audit_log_by_id(self, test_db, sample_audit_log):
        """测试根据ID获取审计日志"""
        response = client.get(f"/admin/logs/{sample_audit_log.id}", headers=ADMIN_HEADERS)
        
        assert response.status_code == 200
        result = response.json()
        
        assert result["id"] == sample_audit_log.id
        assert result["request_id"] == sample_audit_log.request_id
    
    def test_audit_log_filters(self, test_db, sample_audit_log):
        """测试审计日志过滤功能"""
        # 按方法过滤
        response = client.get("/admin/logs?method=POST", headers=ADMIN_HEADERS)
        assert response.status_code == 200
        result = response.json()
        assert len(result) >= 1
        
        # 按状态码过滤
        response = client.get("/admin/logs?status_code=200", headers=ADMIN_HEADERS)
        assert response.status_code == 200
        result = response.json()
        assert len(result) >= 1
        
        # 按API Key过滤
        response = client.get("/admin/logs?api_key=fg_test_key", headers=ADMIN_HEADERS)
        assert response.status_code == 200
        result = response.json()
        assert len(result) >= 1
    
    def test_export_audit_logs(self, test_db, sample_audit_log):
        """测试导出审计日志"""
        # 测试CSV导出
        response = client.get("/admin/logs/export?format=csv", headers=ADMIN_HEADERS)
        assert response.status_code == 200
        assert "text/csv" in response.headers.get("content-type", "")
        
        # 测试JSON导出
        response = client.get("/admin/logs/export?format=json", headers=ADMIN_HEADERS)
        assert response.status_code == 200
        assert "application/json" in response.headers.get("content-type", "")


class TestMetricsAndDashboard:
    """指标和仪表板测试"""
    
    def test_get_metrics(self, test_db):
        """测试获取实时指标"""
        response = client.get("/admin/metrics", headers=ADMIN_HEADERS)
        
        assert response.status_code == 200
        result = response.json()
        
        # 验证指标结构
        assert "total_requests" in result
        assert "total_errors" in result
        assert "success_rate" in result
        assert "average_response_time" in result
        assert "active_api_keys" in result
        assert "active_routes" in result
        assert "top_paths" in result
        assert "status_distribution" in result
    
    def test_get_hourly_metrics(self, test_db):
        """测试获取按小时统计的指标"""
        response = client.get("/admin/metrics/hourly?hours=24", headers=ADMIN_HEADERS)
        
        assert response.status_code == 200
        result = response.json()
        
        assert isinstance(result, list)
    
    def test_get_daily_metrics(self, test_db):
        """测试获取按天统计的指标"""
        response = client.get("/admin/metrics/daily?days=7", headers=ADMIN_HEADERS)
        
        assert response.status_code == 200
        result = response.json()
        
        assert isinstance(result, list)


class TestWebUI:
    """Web UI测试"""
    
    def test_dashboard_page(self):
        """测试仪表板页面"""
        response = client.get("/admin/ui/", headers=ADMIN_HEADERS)
        
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")
        assert "管理面板" in response.text
    
    def test_api_keys_page(self):
        """测试API Key管理页面"""
        response = client.get("/admin/ui/keys", headers=ADMIN_HEADERS)
        
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")
    
    def test_routes_page(self):
        """测试路由配置页面"""
        response = client.get("/admin/ui/routes", headers=ADMIN_HEADERS)
        
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")
    
    def test_logs_page(self):
        """测试审计日志页面"""
        response = client.get("/admin/ui/logs", headers=ADMIN_HEADERS)
        
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")


class TestAuthentication:
    """认证测试"""
    
    def test_admin_token_required(self):
        """测试管理员token认证"""
        # 没有token的请求应该失败
        response = client.get("/admin/keys")
        assert response.status_code == 401
        
        # 错误token的请求应该失败
        bad_headers = {"Authorization": "Bearer wrong-token"}
        response = client.get("/admin/keys", headers=bad_headers)
        assert response.status_code == 401
        
        # 正确token的请求应该成功
        response = client.get("/admin/keys", headers=ADMIN_HEADERS)
        assert response.status_code == 200
    
    def test_invalid_api_endpoints(self):
        """测试无效的API端点"""
        response = client.get("/admin/nonexistent", headers=ADMIN_HEADERS)
        assert response.status_code == 404
        
        response = client.get("/admin/keys/nonexistent", headers=ADMIN_HEADERS)
        assert response.status_code == 404


if __name__ == "__main__":
    # 运行测试
    pytest.main([__file__, "-v"]) 