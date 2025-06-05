"""
路由匹配引擎 - v0.2.0
实现路径模式匹配、请求头和请求体匹配、优先级排序
"""

import re
import json
from typing import Dict, List, Any, Optional
import structlog

logger = structlog.get_logger(__name__)


class RouteMatcher:
    """路由匹配引擎"""
    
    def __init__(self):
        """初始化路由匹配器"""
        self.logger = logger.bind(service="route_matcher")
        self._path_pattern_cache = {}  # 缓存编译的正则表达式
    
    def find_matching_route(
        self, 
        request: Dict[str, Any], 
        routes: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """
        查找匹配的路由
        
        Args:
            request: 请求信息 {"path": str, "method": str, "headers": dict, "body": dict}
            routes: 路由配置列表
            
        Returns:
            Optional[Dict[str, Any]]: 匹配的路由配置，如果没有匹配则返回None
        """
        self.logger.debug(
            "Finding matching route",
            path=request.get("path"),
            method=request.get("method"),
            total_routes=len(routes)
        )
        
        # 过滤活跃路由并按优先级排序
        active_routes = [route for route in routes if route.get("is_active", True)]
        sorted_routes = sorted(active_routes, key=lambda r: r.get("priority", 100))
        
        for route in sorted_routes:
            if self._is_route_match(request, route):
                self.logger.info(
                    "Route matched",
                    route_id=route.get("route_id"),
                    route_name=route.get("route_name"),
                    priority=route.get("priority", 100)
                )
                return route
        
        self.logger.warning("No matching route found", path=request.get("path"))
        return None
    
    def _is_route_match(self, request: Dict[str, Any], route: Dict[str, Any]) -> bool:
        """
        检查请求是否匹配路由
        
        Args:
            request: 请求信息
            route: 路由配置
            
        Returns:
            bool: 是否匹配
        """
        # 路径匹配
        if not self.match_path(request.get("path", ""), route.get("match_path", "")):
            return False
        
        # HTTP方法匹配
        if not self.match_method(request.get("method", ""), route.get("match_method", "ANY")):
            return False
        
        # 请求头匹配
        route_headers = route.get("match_headers")
        if route_headers:
            try:
                match_headers = json.loads(route_headers) if isinstance(route_headers, str) else route_headers
                if not self.match_headers(request.get("headers", {}), match_headers):
                    return False
            except (json.JSONDecodeError, TypeError):
                self.logger.warning("Invalid match_headers format", route_id=route.get("route_id"))
                return False
        
        # 请求体结构匹配
        route_body_schema = route.get("match_body_schema")
        if route_body_schema:
            try:
                body_schema = json.loads(route_body_schema) if isinstance(route_body_schema, str) else route_body_schema
                if not self.match_body_schema(request.get("body", {}), body_schema):
                    return False
            except (json.JSONDecodeError, TypeError):
                self.logger.warning("Invalid match_body_schema format", route_id=route.get("route_id"))
                return False
        
        return True
    
    def match_path(self, request_path: str, route_path: str) -> bool:
        """
        匹配路径
        
        Args:
            request_path: 请求路径
            route_path: 路由路径模式
            
        Returns:
            bool: 是否匹配
        """
        if not route_path:
            return False
        
        # 缓存编译的正则表达式
        if route_path not in self._path_pattern_cache:
            self._path_pattern_cache[route_path] = self._compile_path_pattern(route_path)
        
        pattern = self._path_pattern_cache[route_path]
        return bool(pattern.match(request_path))
    
    def match_method(self, request_method: str, route_method: str) -> bool:
        """
        匹配HTTP方法
        
        Args:
            request_method: 请求方法
            route_method: 路由方法模式
            
        Returns:
            bool: 是否匹配
        """
        if not route_method or route_method.upper() == "ANY":
            return True
        
        # 支持多个方法，用逗号分隔
        allowed_methods = [method.strip().upper() for method in route_method.split(",")]
        return request_method.upper() in allowed_methods
    
    def match_headers(self, request_headers: Dict[str, str], route_headers: Dict[str, str]) -> bool:
        """
        匹配请求头
        
        Args:
            request_headers: 请求头
            route_headers: 路由要求的请求头
            
        Returns:
            bool: 是否匹配
        """
        if not route_headers:
            return True
        
        # 转换为小写进行比较（HTTP头不区分大小写）
        request_headers_lower = {k.lower(): v for k, v in request_headers.items()}
        
        for required_header, required_value in route_headers.items():
            header_key = required_header.lower()
            
            if header_key not in request_headers_lower:
                self.logger.debug(
                    "Required header missing",
                    required_header=required_header
                )
                return False
            
            request_value = request_headers_lower[header_key]
            
            # 支持正则表达式匹配
            if required_value.startswith("regex:"):
                pattern = required_value[6:]  # 移除 "regex:" 前缀
                if not re.search(pattern, request_value, re.IGNORECASE):
                    self.logger.debug(
                        "Header regex mismatch",
                        header=required_header,
                        pattern=pattern,
                        value=request_value
                    )
                    return False
            else:
                # 精确匹配（不区分大小写）
                if request_value.lower() != required_value.lower():
                    self.logger.debug(
                        "Header value mismatch",
                        header=required_header,
                        expected=required_value,
                        actual=request_value
                    )
                    return False
        
        return True
    
    def match_body_schema(self, request_body: Dict[str, Any], body_schema: Dict[str, Any]) -> bool:
        """
        匹配请求体结构（简化的JSON Schema验证）
        
        Args:
            request_body: 请求体
            body_schema: 期望的体结构
            
        Returns:
            bool: 是否匹配
        """
        if not body_schema:
            return True
        
        if not request_body:
            return False
        
        return self._validate_json_schema(request_body, body_schema)
    
    def _compile_path_pattern(self, route_path: str) -> re.Pattern:
        """
        编译路径模式为正则表达式
        
        Args:
            route_path: 路由路径模式
            
        Returns:
            re.Pattern: 编译的正则表达式
        """
        # 转义特殊字符
        escaped = re.escape(route_path)
        
        # 处理通配符
        # * 匹配单个路径段
        # ** 或 {path:path} 匹配多个路径段
        pattern = escaped
        pattern = pattern.replace(r'\*\*', r'.*')  # ** 匹配任意字符
        pattern = pattern.replace(r'\*', r'[^/]*')  # * 匹配除/外的任意字符
        pattern = pattern.replace(r'\{path:path\}', r'.*')  # FastAPI风格路径参数
        
        # 支持路径参数 {param}
        pattern = re.sub(r'\\{[^}]+\\}', r'[^/]+', pattern)
        
        # 确保完全匹配
        pattern = f'^{pattern}$'
        
        try:
            return re.compile(pattern)
        except re.error as e:
            self.logger.error(
                "Failed to compile path pattern",
                route_path=route_path,
                pattern=pattern,
                error=str(e)
            )
            # 回退到精确匹配
            return re.compile(f'^{re.escape(route_path)}$')
    
    def _validate_json_schema(self, data: Dict[str, Any], schema: Dict[str, Any]) -> bool:
        """
        简化的JSON Schema验证
        
        Args:
            data: 要验证的数据
            schema: JSON Schema
            
        Returns:
            bool: 是否符合schema
        """
        try:
            # 检查类型
            expected_type = schema.get("type")
            if expected_type:
                if expected_type == "object" and not isinstance(data, dict):
                    return False
                elif expected_type == "array" and not isinstance(data, list):
                    return False
                elif expected_type == "string" and not isinstance(data, str):
                    return False
                elif expected_type == "number" and not isinstance(data, (int, float)):
                    return False
                elif expected_type == "boolean" and not isinstance(data, bool):
                    return False
            
            # 检查必需属性
            required_properties = schema.get("required", [])
            if isinstance(data, dict):
                for prop in required_properties:
                    if prop not in data:
                        self.logger.debug(
                            "Required property missing",
                            property=prop
                        )
                        return False
            
            # 检查属性类型
            properties = schema.get("properties", {})
            if isinstance(data, dict) and properties:
                for prop, prop_schema in properties.items():
                    if prop in data:
                        if not self._validate_json_schema(data[prop], prop_schema):
                            return False
            
            # 检查数组项
            if isinstance(data, list) and "items" in schema:
                item_schema = schema["items"]
                for item in data:
                    if not self._validate_json_schema(item, item_schema):
                        return False
            
            return True
            
        except Exception as e:
            self.logger.error(
                "Error during schema validation",
                error=str(e),
                schema=schema
            )
            return False
    
    def get_route_priority_score(self, route: Dict[str, Any]) -> int:
        """
        计算路由优先级分数（分数越低优先级越高）
        
        Args:
            route: 路由配置
            
        Returns:
            int: 优先级分数
        """
        # 基础优先级
        score = route.get("priority", 100)
        
        # 精确路径匹配加分（优先级更高）
        match_path = route.get("match_path", "")
        if "*" not in match_path and "{" not in match_path:
            score -= 10
        
        # 有方法限制加分
        match_method = route.get("match_method", "ANY")
        if match_method != "ANY":
            score -= 5
        
        # 有请求头匹配加分
        if route.get("match_headers"):
            score -= 3
        
        # 有请求体匹配加分
        if route.get("match_body_schema"):
            score -= 2
        
        return score
    
    def clear_cache(self):
        """清空路径模式缓存"""
        self._path_pattern_cache.clear()
        self.logger.debug("Path pattern cache cleared") 