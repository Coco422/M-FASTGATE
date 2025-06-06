"""
路由匹配器请求体模式匹配测试 - v0.2.0
专门测试 match_body_schema 功能，包括简单键值对匹配和标准JSON Schema验证
"""

import os
import sys
import json
import pytest
from typing import Dict, Any

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.services.route_matcher import RouteMatcher


class TestRouteMatcherBodySchema:
    """路由匹配器请求体模式匹配测试类"""
    
    @pytest.fixture
    def matcher(self):
        """路由匹配器实例"""
        return RouteMatcher()
    
    @pytest.fixture
    def sample_request_body(self):
        """示例请求体"""
        return {
            "model": "test-model",
            "messages": [
                {"role": "user", "content": "Hello"}
            ],
            "temperature": 0.7,
            "stream": False
        }
    
    def test_simple_key_value_matching_success(self, matcher, sample_request_body):
        """测试简单键值对匹配 - 成功情况"""
        # 测试单个字段匹配
        schema = {"model": "test-model"}
        assert matcher.match_body_schema(sample_request_body, schema) is True
        
        # 测试多个字段匹配
        schema_multi = {"model": "test-model", "stream": False}
        assert matcher.match_body_schema(sample_request_body, schema_multi) is True
    
    def test_simple_key_value_matching_failure(self, matcher, sample_request_body):
        """测试简单键值对匹配 - 失败情况"""
        # 值不匹配
        schema_wrong_value = {"model": "wrong-model"}
        assert matcher.match_body_schema(sample_request_body, schema_wrong_value) is False
        
        # 字段缺失
        schema_missing_field = {"non_existent_field": "value"}
        assert matcher.match_body_schema(sample_request_body, schema_missing_field) is False
        
        # 部分字段匹配，部分不匹配
        schema_partial = {"model": "test-model", "stream": True}  # stream值不匹配
        assert matcher.match_body_schema(sample_request_body, schema_partial) is False
    
    def test_empty_schema_matching(self, matcher, sample_request_body):
        """测试空模式匹配 - 应该总是成功"""
        empty_schema = {}
        assert matcher.match_body_schema(sample_request_body, empty_schema) is True
    
    def test_none_schema_matching(self, matcher, sample_request_body):
        """测试None模式匹配 - 应该总是成功"""
        none_schema = None
        assert matcher.match_body_schema(sample_request_body, none_schema) is True
    
    def test_empty_request_body_matching(self, matcher):
        """测试空请求体匹配"""
        empty_body = {}
        
        # 空请求体 + 空模式 = 匹配成功
        empty_schema = {}
        assert matcher.match_body_schema(empty_body, empty_schema) is True
        
        # 空请求体 + 有要求的模式 = 匹配失败
        required_schema = {"model": "test"}
        assert matcher.match_body_schema(empty_body, required_schema) is False
    
    def test_json_schema_validation(self, matcher):
        """测试标准JSON Schema验证"""
        # 带有JSON Schema关键字的复杂验证
        json_schema = {
            "type": "object",
            "properties": {
                "model": {"type": "string"},
                "temperature": {"type": "number"}
            },
            "required": ["model"]
        }
        
        # 符合schema的请求体
        valid_body = {"model": "test", "temperature": 0.7}
        assert matcher.match_body_schema(valid_body, json_schema) is True
        
        # 缺少必需字段
        invalid_body_missing = {"temperature": 0.7}
        assert matcher.match_body_schema(invalid_body_missing, json_schema) is False
        
        # 类型不匹配
        invalid_body_type = {"model": 123, "temperature": 0.7}
        assert matcher.match_body_schema(invalid_body_type, json_schema) is False
    
    def test_route_matching_with_body_schema(self, matcher):
        """测试完整的路由匹配过程中的body schema验证"""
        routes = [
            {
                "route_id": "v2-model-a",
                "match_path": "/v2*",
                "match_method": "POST",
                "match_body_schema": '{"model": "model-a"}',
                "target_host": "host1:8080",
                "priority": 50,
                "is_active": True
            },
            {
                "route_id": "v2-model-b", 
                "match_path": "/v2*",
                "match_method": "POST",
                "match_body_schema": '{"model": "model-b"}',
                "target_host": "host2:8080",
                "priority": 50,
                "is_active": True
            },
            {
                "route_id": "v2-fallback",
                "match_path": "/v2*",
                "match_method": "POST",
                "match_body_schema": None,  # 无body要求
                "target_host": "fallback:8080",
                "priority": 100,  # 低优先级
                "is_active": True
            }
        ]
        
        # 请求1: 匹配model-a路由
        request1 = {
            "path": "/v2/chat/completions",
            "method": "POST",
            "headers": {"content-type": "application/json"},
            "body": {"model": "model-a", "messages": []}
        }
        
        matched_route1 = matcher.find_matching_route(request1, routes)
        assert matched_route1 is not None
        assert matched_route1["route_id"] == "v2-model-a"
        
        # 请求2: 匹配model-b路由
        request2 = {
            "path": "/v2/chat/completions", 
            "method": "POST",
            "headers": {"content-type": "application/json"},
            "body": {"model": "model-b", "messages": []}
        }
        
        matched_route2 = matcher.find_matching_route(request2, routes)
        assert matched_route2 is not None
        assert matched_route2["route_id"] == "v2-model-b"
        
        # 请求3: 不匹配特定model，应该匹配fallback路由
        request3 = {
            "path": "/v2/chat/completions",
            "method": "POST", 
            "headers": {"content-type": "application/json"},
            "body": {"model": "unknown-model", "messages": []}
        }
        
        matched_route3 = matcher.find_matching_route(request3, routes)
        assert matched_route3 is not None
        assert matched_route3["route_id"] == "v2-fallback"
    
    def test_multiple_field_matching(self, matcher):
        """测试多字段匹配"""
        request_body = {
            "model": "gpt-4",
            "stream": True,
            "temperature": 0.8,
            "max_tokens": 100
        }
        
        # 匹配多个字段
        schema = {"model": "gpt-4", "stream": True}
        assert matcher.match_body_schema(request_body, schema) is True
        
        # 其中一个字段不匹配
        schema_fail = {"model": "gpt-4", "stream": False}
        assert matcher.match_body_schema(request_body, schema_fail) is False
    
    def test_nested_object_simple_matching(self, matcher):
        """测试嵌套对象的简单匹配"""
        request_body = {
            "model": "test",
            "config": {
                "temperature": 0.7,
                "max_tokens": 100
            }
        }
        
        # 简单键值对不支持嵌套匹配（这是预期行为）
        schema = {"model": "test"}
        assert matcher.match_body_schema(request_body, schema) is True
    
    def test_array_field_matching(self, matcher):
        """测试数组字段匹配"""
        request_body = {
            "model": "test",
            "messages": [
                {"role": "user", "content": "hello"}
            ]
        }
        
        # 简单匹配数组字段
        schema = {"model": "test"}
        assert matcher.match_body_schema(request_body, schema) is True
    
    def test_boolean_and_numeric_matching(self, matcher):
        """测试布尔值和数字值匹配"""
        request_body = {
            "model": "test",
            "stream": True,
            "temperature": 0.7,
            "max_tokens": 100
        }
        
        # 布尔值匹配
        schema_bool = {"stream": True}
        assert matcher.match_body_schema(request_body, schema_bool) is True
        
        schema_bool_false = {"stream": False}
        assert matcher.match_body_schema(request_body, schema_bool_false) is False
        
        # 数字值匹配
        schema_num = {"temperature": 0.7}
        assert matcher.match_body_schema(request_body, schema_num) is True
        
        schema_num_wrong = {"temperature": 0.8}
        assert matcher.match_body_schema(request_body, schema_num_wrong) is False
        
        # 整数匹配
        schema_int = {"max_tokens": 100}
        assert matcher.match_body_schema(request_body, schema_int) is True
    
    def test_case_sensitivity(self, matcher):
        """测试大小写敏感性"""
        request_body = {"model": "Test-Model"}
        
        # 值必须完全匹配（大小写敏感）
        schema_exact = {"model": "Test-Model"}
        assert matcher.match_body_schema(request_body, schema_exact) is True
        
        schema_wrong_case = {"model": "test-model"}
        assert matcher.match_body_schema(request_body, schema_wrong_case) is False
    
    def test_priority_based_routing(self, matcher):
        """测试基于优先级的路由选择"""
        routes = [
            {
                "route_id": "specific-route",
                "match_path": "/v2/chat/completions",
                "match_method": "POST",
                "match_body_schema": '{"model": "gpt-4", "stream": true}',
                "priority": 10,  # 高优先级
                "is_active": True
            },
            {
                "route_id": "general-route",
                "match_path": "/v2*",
                "match_method": "POST", 
                "match_body_schema": '{"model": "gpt-4"}',
                "priority": 50,  # 低优先级
                "is_active": True
            }
        ]
        
        # 两个路由都匹配，应该选择优先级更高的
        request = {
            "path": "/v2/chat/completions",
            "method": "POST",
            "headers": {},
            "body": {"model": "gpt-4", "stream": True, "messages": []}
        }
        
        matched_route = matcher.find_matching_route(request, routes)
        assert matched_route is not None
        assert matched_route["route_id"] == "specific-route" 