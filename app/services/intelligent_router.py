"""
智能路由服务
"""

import time
import asyncio
from typing import Optional, Dict, Any
from fastapi import Request, HTTPException, status
from sqlalchemy.orm import Session

from ..models.model_endpoint import RouteResult, CloudProxyConfig
from ..models.audit_log import generate_request_id
from .model_route_manager import ModelRouteManager
from .request_enhancer import RequestEnhancer
from ..config import settings


class IntelligentRouter:
    """智能路由器"""
    
    def __init__(self, db: Session):
        self.db = db
        self.route_manager = ModelRouteManager(db)
        self.request_enhancer = RequestEnhancer()
        self.cloud_proxy = CloudProxyConfig()
    
    async def route_request(
        self, 
        request: Request,
        request_body: Dict[str, Any], 
        api_key: str,
        source_path: str
    ) -> RouteResult:
        """
        执行智能路由
        
        Args:
            request: FastAPI请求对象
            request_body: 请求体
            api_key: API密钥
            source_path: 来源路径
            
        Returns:
            RouteResult: 路由结果
            
        Raises:
            HTTPException: 路由失败时抛出异常
        """
        routing_start_time = time.time()
        
        try:
            # 1. 提取模型名称
            model_name = self.request_enhancer.extract_model_name(request_body)
            
            # 2. 获取路由配置
            endpoint = self.route_manager.get_endpoint(model_name)
            if not endpoint:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"No route configured for model: {model_name}"
                )
            
            # 3. 验证请求
            if not self.request_enhancer.validate_request_for_model(request_body, endpoint):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid request format for model: {model_name}"
                )
            
            # 4. 应用参数默认值
            enhanced_body = self.request_enhancer.apply_parameter_defaults(request_body, endpoint)
            
            # 5. 增强请求
            enhanced_body, enhanced_headers = self.request_enhancer.enhance_request(
                enhanced_body, endpoint, dict(request.headers)
            )
            
            # 6. 构建目标URL
            target_url = self._build_target_url(request, endpoint)
            
            routing_time_ms = int((time.time() - routing_start_time) * 1000)
            
            return RouteResult(
                target_url=target_url,
                enhanced_body=enhanced_body,
                enhanced_headers=enhanced_headers,
                endpoint_config=endpoint
            )
            
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Routing failed: {str(e)}"
            )
    
    def _build_target_url(self, request: Request, endpoint) -> str:
        """
        构建目标URL
        
        Args:
            request: 原始请求
            endpoint: 模型端点配置
            
        Returns:
            str: 目标URL
        """
        base_url = f"http://{self.cloud_proxy.host}:{self.cloud_proxy.port}{self.cloud_proxy.base_path}"
        
        if endpoint.endpoint_type == "embedding":
            # 嵌入模型使用固定的/embed端点
            return f"{base_url}/embed"
        else:
            # Chat模型需要去掉智能路由前缀，保留实际的API路径
            original_path = request.url.path
            
            # 移除/smart前缀（智能路由标识）
            if original_path.startswith("/smart/"):
                original_path = original_path[6:]  # 移除"/smart"，保留后面的"/"
            elif original_path.startswith("/smart"):
                original_path = original_path[6:]  # 移除"/smart"
            
            # 移除/proxy前缀（如果存在）
            if original_path.startswith("/proxy/"):
                original_path = original_path[7:]  # 移除"/proxy/"
            elif original_path.startswith("/proxy"):
                original_path = original_path[6:]  # 移除"/proxy"
            
            # 确保路径以/开头
            if not original_path.startswith("/"):
                original_path = "/" + original_path
            
            return f"{base_url}{original_path}"
    
    def get_available_models(self) -> Dict[str, Any]:
        """
        获取可用模型信息
        
        Returns:
            Dict: 模型信息
        """
        chat_models = self.route_manager.get_models_by_type("chat")
        embedding_models = self.route_manager.get_models_by_type("embedding")
        
        return {
            "chat_models": chat_models,
            "embedding_models": embedding_models,
            "total_models": len(chat_models) + len(embedding_models),
            "cloud_proxy": {
                "host": self.cloud_proxy.host,
                "port": self.cloud_proxy.port,
                "base_path": self.cloud_proxy.base_path
            }
        }
    
    def get_model_info(self, model_name: str) -> Optional[Dict[str, Any]]:
        """
        获取指定模型的详细信息
        
        Args:
            model_name: 模型名称
            
        Returns:
            Optional[Dict]: 模型信息
        """
        route = self.route_manager.get_route_by_model(model_name)
        if not route:
            return None
        
        return {
            "model_name": route.model_name,
            "endpoint_type": route.endpoint_type,
            "proxy_path": route.proxy_path,
            "parameters": route.parameters,
            "timeout": route.timeout,
            "max_retries": route.max_retries,
            "is_active": route.is_active,
            "health_status": route.health_status,
            "target_base_url": f"http://{self.cloud_proxy.host}:{self.cloud_proxy.port}{self.cloud_proxy.base_path}"
        }
    
    def validate_model_request(self, model_name: str, request_body: Dict[str, Any]) -> Dict[str, Any]:
        """
        验证模型请求
        
        Args:
            model_name: 模型名称
            request_body: 请求体
            
        Returns:
            Dict: 验证结果
        """
        endpoint = self.route_manager.get_endpoint(model_name)
        if not endpoint:
            return {
                "valid": False,
                "error": f"Model '{model_name}' not found or inactive"
            }
        
        # 检查请求体中的模型名称
        try:
            body_model = self.request_enhancer.extract_model_name(request_body)
            if body_model != model_name:
                return {
                    "valid": False,
                    "error": f"Model name mismatch: URL has '{model_name}', body has '{body_model}'"
                }
        except ValueError as e:
            return {
                "valid": False,
                "error": str(e)
            }
        
        # 验证请求格式
        if not self.request_enhancer.validate_request_for_model(request_body, endpoint):
            return {
                "valid": False,
                "error": f"Invalid request format for {endpoint.endpoint_type} model"
            }
        
        return {
            "valid": True,
            "endpoint_type": endpoint.endpoint_type,
            "recommended_params": self.request_enhancer.get_recommended_parameters(endpoint)
        }
    
    async def health_check_model(self, model_name: str) -> Dict[str, Any]:
        """
        检查指定模型的健康状态
        
        Args:
            model_name: 模型名称
            
        Returns:
            Dict: 健康检查结果
        """
        endpoint = self.route_manager.get_endpoint(model_name)
        if not endpoint:
            return {
                "model_name": model_name,
                "status": "not_found",
                "message": "Model not configured"
            }
        
        # 构建健康检查URL
        health_url = f"http://{self.cloud_proxy.host}:{self.cloud_proxy.port}{endpoint.health_check_path}"
        
        try:
            import httpx
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(health_url)
                
                if response.status_code == 200:
                    return {
                        "model_name": model_name,
                        "status": "healthy",
                        "response_time_ms": response.elapsed.total_seconds() * 1000,
                        "message": "Model is responding"
                    }
                else:
                    return {
                        "model_name": model_name,
                        "status": "unhealthy",
                        "status_code": response.status_code,
                        "message": f"Health check failed with status {response.status_code}"
                    }
                    
        except Exception as e:
            return {
                "model_name": model_name,
                "status": "error",
                "message": f"Health check error: {str(e)}"
            } 