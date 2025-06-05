"""
请求增强服务
"""

from typing import Dict, Any, Tuple
from ..models.model_endpoint import ModelEndpointConfig, CloudProxyConfig
from ..config import settings


class RequestEnhancer:
    """请求增强器"""
    
    def __init__(self):
        self.cloud_proxy = CloudProxyConfig()
        self.app_key = getattr(settings.model_routing, 'app_key', 'your_model_app_key_here')
        self.system_source = getattr(settings.model_routing, 'system_source', '智能客服系统')
    
    def enhance_request(
        self, 
        request_body: Dict[str, Any], 
        endpoint: ModelEndpointConfig,
        original_headers: Dict[str, str]
    ) -> Tuple[Dict[str, Any], Dict[str, str]]:
        """
        增强请求体和请求头
        
        Args:
            request_body: 原始请求体
            endpoint: 模型端点配置
            original_headers: 原始请求头
            
        Returns:
            Tuple[Dict, Dict]: (增强后的请求体, 增强后的请求头)
        """
        
        # 增强请求体
        enhanced_body = request_body.copy()
        enhanced_body.update({
            "systemSource": self.system_source,
            "modelIp": self.cloud_proxy.host,      # 云天代理IP
            "modelPort": self.cloud_proxy.port,    # 云天代理端口
            "modelName": endpoint.model_name
        })
        
        # 增强请求头
        enhanced_headers = original_headers.copy()
        enhanced_headers.update({
            "appKey": self.app_key,
            "User-Agent": f"M-FastGate/{settings.app.version}",
            "X-Forwarded-By": "M-FastGate",
            "Content-Type": "application/json"
        })
        
        # 移除可能冲突的头部
        headers_to_remove = ["host", "content-length", "transfer-encoding"]
        for header in headers_to_remove:
            enhanced_headers.pop(header, None)
            enhanced_headers.pop(header.title(), None)
        
        return enhanced_body, enhanced_headers
    
    def extract_model_name(self, request_body: Dict[str, Any]) -> str:
        """
        从请求体中提取模型名称
        
        Args:
            request_body: 请求体
            
        Returns:
            str: 模型名称
            
        Raises:
            ValueError: 如果请求体中没有model字段
        """
        model_name = request_body.get("model")
        if not model_name:
            raise ValueError("Request body must contain 'model' field")
        
        return model_name
    
    def validate_request_for_model(
        self, 
        request_body: Dict[str, Any], 
        endpoint: ModelEndpointConfig
    ) -> bool:
        """
        验证请求是否适合指定的模型
        
        Args:
            request_body: 请求体
            endpoint: 模型端点配置
            
        Returns:
            bool: 验证结果
        """
        
        # 验证模型名称匹配
        try:
            model_name = self.extract_model_name(request_body)
            if model_name != endpoint.model_name:
                return False
        except ValueError:
            return False
        
        # 根据端点类型验证请求结构
        if endpoint.endpoint_type == "chat":
            # Chat模型需要messages字段
            if "messages" not in request_body:
                return False
        elif endpoint.endpoint_type == "embedding":
            # Embedding模型需要input字段
            if "input" not in request_body:
                return False
            
            # 检查输入长度限制（如果配置了）
            if endpoint.parameters and "max_input_tokens" in endpoint.parameters:
                max_tokens = endpoint.parameters["max_input_tokens"]
                input_text = request_body.get("input", "")
                # 简单的token估算（实际应该使用tokenizer）
                estimated_tokens = len(input_text.split()) if isinstance(input_text, str) else 0
                if estimated_tokens > max_tokens:
                    return False
        
        return True
    
    def get_recommended_parameters(self, endpoint: ModelEndpointConfig) -> Dict[str, Any]:
        """
        获取模型的推荐参数
        
        Args:
            endpoint: 模型端点配置
            
        Returns:
            Dict: 推荐参数
        """
        if not endpoint.parameters:
            return {}
        
        recommended = {}
        
        # 提取推荐参数
        if "recommended_temperature" in endpoint.parameters:
            recommended["temperature"] = endpoint.parameters["recommended_temperature"]
        
        if "recommended_top_p" in endpoint.parameters:
            recommended["top_p"] = endpoint.parameters["recommended_top_p"]
        
        return recommended
    
    def apply_parameter_defaults(
        self, 
        request_body: Dict[str, Any], 
        endpoint: ModelEndpointConfig
    ) -> Dict[str, Any]:
        """
        应用参数默认值
        
        Args:
            request_body: 请求体
            endpoint: 模型端点配置
            
        Returns:
            Dict: 应用默认值后的请求体
        """
        enhanced_body = request_body.copy()
        recommended = self.get_recommended_parameters(endpoint)
        
        # 只在用户没有指定时应用推荐值
        for param, value in recommended.items():
            if param not in enhanced_body:
                enhanced_body[param] = value
        
        return enhanced_body 