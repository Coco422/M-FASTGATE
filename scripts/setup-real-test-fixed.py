#!/usr/bin/env python3
"""
M-FastGate v0.2.0 真实测试用例设置脚本（修正版）
正确配置网关密钥和后端API密钥的映射关系
"""

import sys
import os
import secrets
from pathlib import Path
from datetime import datetime, timedelta

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.database import get_db, create_tables
from app.models.api_key import APIKeyDB, APIKeyCreate, generate_api_key
from app.models.proxy_route import ProxyRouteDB
from app.services.key_manager import KeyManager
from app.config import settings


def setup_real_test_case_fixed():
    """设置真实测试用例（修正版）"""
    print("🚀 设置M-FastGate v0.2.0真实测试用例（修正版）")
    print("=" * 70)
    
    # 真实后端服务信息
    backend_api_key = "sk-nsItInRUqh7KFKX8l3xVOvLVaRJQo1iNi6ALl6rBUjqTdgFc"
    target_host = "172.16.99.204"
    target_port = "3398"
    target_path = "/v1"
    model_name = "mckj/Qwen3-30B-A3B"
    
    print(f"🔧 后端API密钥: {backend_api_key}")
    print(f"🌐 目标主机: {target_host}:{target_port}")
    print(f"📋 目标路径: {target_path}")
    print(f"🤖 模型名称: {model_name}")
    print("-" * 70)
    
    try:
        # 创建数据库表
        print("📊 创建数据库表...")
        create_tables()
        print("✅ 数据库表创建成功")
        
        db = next(get_db())
        
        # 1. 创建网关API密钥（供用户使用）
        print(f"\n🔑 创建网关API密钥...")
        
        key_manager = KeyManager(db)
        
        # 创建网关密钥
        from app.models.api_key import APIKeyCreate
        gateway_key_data = APIKeyCreate(
            source_path="qwen3-30b-gateway",
            permissions=["chat.completions", "models.list"],
            expires_days=365,
            rate_limit=1000
        )
        
        gateway_key = key_manager.create_key(gateway_key_data)
        print(f"✅ 创建网关密钥成功")
        print(f"   密钥ID: {gateway_key.key_id}")
        print(f"   密钥值: {gateway_key.key_value}")
        print(f"   来源路径: {gateway_key.source_path}")
        
        # 2. 创建代理路由配置（包含后端密钥）
        print(f"\n🛣️  创建代理路由配置...")
        
        # 删除可能存在的测试路由
        existing_routes = db.query(ProxyRouteDB).filter(
            ProxyRouteDB.route_id.like("qwen3-30b%")
        ).all()
        
        for route in existing_routes:
            db.delete(route)
        db.commit()
        
        # 创建聊天完成路由（包含后端API密钥转换）
        chat_route = ProxyRouteDB(
            route_id="qwen3-30b-chat",
            route_name="Qwen3-30B Chat Completions",
            description=f"Qwen3-30B模型聊天完成接口 - {target_host}:{target_port}",
            match_path="/v1/chat/completions",
            match_method="POST",
            match_body_schema='{"model": "mckj/Qwen3-30B-A3B"}',
            target_host=f"{target_host}:{target_port}",
            target_path="/v1/chat/completions",
            target_protocol="http",
            strip_path_prefix=False,
            # 关键：在转发时将Authorization头替换为真实的后端API密钥
            add_headers=f'{{"Authorization": "Bearer {backend_api_key}", "X-Proxy-Source": "M-FastGate-v0.2.0"}}',
            add_body_fields='{"source": "fastgate"}',
            remove_headers='["host"]',
            is_active=True,
            priority=100
        )
        
        db.add(chat_route)
        db.commit()
        print(f"✅ 创建聊天完成路由: {chat_route.route_id}")
        
        # 创建通用API路由（兼容其他路径）
        general_route = ProxyRouteDB(
            route_id="qwen3-30b-general",
            route_name="Qwen3-30B General API",
            description=f"Qwen3-30B模型通用API代理 - {target_host}:{target_port}",
            match_path="/v1/.*",
            match_method="ANY",
            match_body_schema=None,
            target_host=f"{target_host}:{target_port}",
            target_path="/v1/",
            target_protocol="http",
            strip_path_prefix=True,
            # 通用路由也替换API密钥
            add_headers=f'{{"Authorization": "Bearer {backend_api_key}", "X-Proxy-Source": "M-FastGate-v0.2.0"}}',
            add_body_fields=None,
            remove_headers='["host"]',
            is_active=True,
            priority=200
        )
        
        db.add(general_route)
        db.commit()
        print(f"✅ 创建通用API路由: {general_route.route_id}")
        
        # 3. 验证设置
        print(f"\n🔍 验证设置...")
        
        # 验证API密钥
        key_count = db.query(APIKeyDB).filter(APIKeyDB.is_active == True).count()
        print(f"📊 活跃API密钥数量: {key_count}")
        
        # 验证代理路由
        route_count = db.query(ProxyRouteDB).filter(ProxyRouteDB.is_active == True).count()
        print(f"📊 活跃代理路由数量: {route_count}")
        
        # 显示配置的路由
        active_routes = db.query(ProxyRouteDB).filter(ProxyRouteDB.is_active == True).all()
        print(f"\n📋 活跃的代理路由:")
        for route in active_routes:
            print(f"   - {route.route_name} ({route.route_id})")
            print(f"     路径: {route.match_path}")
            print(f"     目标: {route.target_protocol}://{route.target_host}{route.target_path}")
            print(f"     已配置后端密钥: ✅")
        
        db.close()
        
        print(f"\n🎉 真实测试用例设置完成（修正版）！")
        print(f"=" * 70)
        print(f"✅ 现在可以使用以下信息测试系统:")
        print(f"   🔑 网关API密钥: {gateway_key.key_value}")
        print(f"   🌍 请求URL: http://localhost:8514/v1/chat/completions")
        print(f"   🤖 模型名称: {model_name}")
        print(f"   🔧 后端服务: http://{target_host}:{target_port}{target_path}")
        print(f"   🔐 后端密钥: {backend_api_key[:20]}...")
        
        return gateway_key.key_value
        
    except Exception as e:
        print(f"❌ 设置失败: {e}")
        import traceback
        traceback.print_exc()
        return None


def create_test_request_example_fixed(gateway_key: str):
    """创建修正版测试请求示例"""
    print(f"\n📝 测试请求示例（使用网关密钥）:")
    
    curl_example = f"""
# 使用curl测试（注意：使用网关密钥，不是后端密钥）
curl -X POST http://localhost:8514/v1/chat/completions \\
  -H "Content-Type: application/json" \\
  -H "Authorization: Bearer {gateway_key}" \\
  -d '{{
    "model": "mckj/Qwen3-30B-A3B",
    "messages": [
      {{"role": "user", "content": "Hello, how are you?"}}
    ],
    "max_tokens": 100,
    "temperature": 0.7
  }}'

# 流式请求测试
curl -X POST http://localhost:8514/v1/chat/completions \\
  -H "Content-Type: application/json" \\
  -H "Authorization: Bearer {gateway_key}" \\
  -d '{{
    "model": "mckj/Qwen3-30B-A3B",
    "messages": [
      {{"role": "user", "content": "Tell me a short story"}}
    ],
    "max_tokens": 200,
    "temperature": 0.7,
    "stream": true
  }}'
"""
    
    print(curl_example)
    
    python_example = f"""
# Python测试代码（使用网关密钥）
import requests

url = "http://localhost:8514/v1/chat/completions"
headers = {{
    "Content-Type": "application/json",
    "Authorization": "Bearer {gateway_key}"  # 网关密钥，不是后端密钥
}}

data = {{
    "model": "mckj/Qwen3-30B-A3B",
    "messages": [
        {{"role": "user", "content": "Hello, how are you?"}}
    ],
    "max_tokens": 100,
    "temperature": 0.7
}}

response = requests.post(url, json=data, headers=headers)
print(response.json())
"""
    
    print(python_example)


if __name__ == "__main__":
    gateway_key = setup_real_test_case_fixed()
    
    if gateway_key:
        create_test_request_example_fixed(gateway_key)
        print(f"\n🚀 启动服务器测试:")
        print(f"   cd /data/yangr/gitRepos/M-FastGate")
        print(f"   python -m app.main")
        print(f"\n📌 重要说明:")
        print(f"   - 用户使用网关密钥: {gateway_key}")
        print(f"   - 网关自动转换为后端密钥: sk-nsItInRUqh7KFKX8l3xVOvLVaRJQo1iNi6ALl6rBUjqTdgFc")
        print(f"   - 用户无需知道真实的后端API密钥")
        sys.exit(0)
    else:
        sys.exit(1) 