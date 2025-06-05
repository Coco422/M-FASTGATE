#!/usr/bin/env python3
"""
M-FastGate v0.2.0 真实测试用例设置脚本
设置用户提供的OpenAI兼容API接口
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
from app.models.api_key import APIKeyDB, APIKeyCreate
from app.models.proxy_route import ProxyRouteDB
from app.services.key_manager import KeyManager
from app.config import settings


def setup_real_test_case():
    """设置真实测试用例"""
    print("🚀 设置M-FastGate v0.2.0真实测试用例")
    print("=" * 60)
    
    # 测试用例信息
    test_key = "sk-nsItInRUqh7KFKX8l3xVOvLVaRJQo1iNi6ALl6rBUjqTdgFc"
    target_host = "172.16.99.204"
    target_port = "3398"
    target_path = "/v1"
    model_name = "mckj/Qwen3-30B-A3B"
    
    print(f"🔑 API密钥: {test_key}")
    print(f"🌐 目标主机: {target_host}:{target_port}")
    print(f"📋 目标路径: {target_path}")
    print(f"🤖 模型名称: {model_name}")
    print("-" * 60)
    
    try:
        # 创建数据库表
        print("📊 创建数据库表...")
        create_tables()
        print("✅ 数据库表创建成功")
        
        db = next(get_db())
        
        # 1. 创建API密钥
        print(f"\n🔑 创建API密钥...")
        
        # 检查密钥是否已存在
        existing_key = db.query(APIKeyDB).filter(APIKeyDB.key_value == test_key).first()
        if existing_key:
            print(f"⚠️  密钥已存在，ID: {existing_key.key_id}")
            api_key_id = existing_key.key_id
        else:
            # 手动创建密钥记录（使用真实密钥）
            api_key = APIKeyDB(
                key_id=f"fg_{secrets.token_hex(8)}",
                key_value=test_key,
                source_path="real-test",
                is_active=True,
                expires_at=datetime.utcnow() + timedelta(days=365)
            )
            
            db.add(api_key)
            db.commit()
            db.refresh(api_key)
            api_key_id = api_key.key_id
            print(f"✅ 创建API密钥成功，ID: {api_key_id}")
        
        # 2. 创建代理路由配置
        print(f"\n🛣️  创建代理路由配置...")
        
        # 删除可能存在的测试路由
        existing_routes = db.query(ProxyRouteDB).filter(
            ProxyRouteDB.route_id.like("qwen3-30b%")
        ).all()
        
        for route in existing_routes:
            db.delete(route)
        db.commit()
        
        # 创建通用chat completions路由
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
            add_headers='{"X-Proxy-Source": "M-FastGate-v0.2.0"}',
            add_body_fields='{"source": "fastgate"}',
            remove_headers='["host"]',
            is_active=True,
            priority=100
        )
        
        db.add(chat_route)
        db.commit()
        print(f"✅ 创建聊天完成路由: {chat_route.route_id}")
        
        # 创建通用模型路由（兼容其他路径）
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
            add_headers='{"X-Proxy-Source": "M-FastGate-v0.2.0"}',
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
        
        db.close()
        
        print(f"\n🎉 真实测试用例设置完成！")
        print(f"=" * 60)
        print(f"✅ 现在可以使用以下信息测试系统:")
        print(f"   API密钥: {test_key}")
        print(f"   请求URL: http://localhost:8514/v1/chat/completions")
        print(f"   模型名称: {model_name}")
        print(f"   目标服务: http://{target_host}:{target_port}{target_path}")
        
        return True
        
    except Exception as e:
        print(f"❌ 设置失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def create_test_request_example():
    """创建测试请求示例"""
    print(f"\n📝 测试请求示例:")
    
    curl_example = f"""
# 使用curl测试
curl -X POST http://localhost:8514/v1/chat/completions \\
  -H "Content-Type: application/json" \\
  -H "Authorization: Bearer sk-nsItInRUqh7KFKX8l3xVOvLVaRJQo1iNi6ALl6rBUjqTdgFc" \\
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
  -H "Authorization: Bearer sk-nsItInRUqh7KFKX8l3xVOvLVaRJQo1iNi6ALl6rBUjqTdgFc" \\
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
# Python测试代码
import requests

url = "http://localhost:8514/v1/chat/completions"
headers = {{
    "Content-Type": "application/json",
    "Authorization": "Bearer sk-nsItInRUqh7KFKX8l3xVOvLVaRJQo1iNi6ALl6rBUjqTdgFc"
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
    success = setup_real_test_case()
    
    if success:
        create_test_request_example()
        print(f"\n🚀 启动服务器测试:")
        print(f"   cd /data/yangr/gitRepos/M-FastGate")
        print(f"   python -m app.main")
        sys.exit(0)
    else:
        sys.exit(1) 