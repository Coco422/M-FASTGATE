#!/usr/bin/env python3
"""
创建API Key的便捷脚本
"""

import requests
import json
import sys

def create_api_key(base_url, admin_token, user_name, expires_days=30):
    """创建单个API Key"""
    
    url = f"{base_url}/admin/keys"
    params = {"token": admin_token}
    
    data = {
        "source_path": user_name,
        "permissions": ["chat"],
        "expires_days": expires_days
    }
    
    try:
        response = requests.post(url, params=params, json=data)
        
        if response.status_code == 200:
            key_info = response.json()
            print(f"✅ 成功为 {user_name} 创建API Key:")
            print(f"   Key ID: {key_info['key_id']}")
            print(f"   Key Value: {key_info['key_value']}")
            print(f"   过期时间: {key_info['expires_at']}")
            print("-" * 60)
            return key_info
        else:
            print(f"❌ 创建API Key失败 ({response.status_code}): {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ 请求失败: {e}")
        return None

def main():
    """主函数"""
    
    # 配置
    BASE_URL = "http://localhost:8514"
    ADMIN_TOKEN = "admin_secret_token_dev"
    
    # 检查服务是否运行
    try:
        response = requests.get(f"{BASE_URL}/health")
        if response.status_code != 200:
            print("❌ M-FastGate 服务未运行，请先启动服务")
            return
    except:
        print("❌ 无法连接到 M-FastGate 服务，请确认服务已启动")
        return
    
    print("🔑 M-FastGate API Key 创建工具")
    print("=" * 50)
    
    # 获取用户输入
    if len(sys.argv) > 1:
        # 命令行参数模式
        users = sys.argv[1:]
    else:
        # 交互模式
        print("请输入要创建API Key的用户名，用空格分隔 (例如: user1 user2 user3):")
        user_input = input("> ").strip()
        if not user_input:
            users = ["user1", "user2", "user3"]  # 默认用户
            print(f"使用默认用户: {' '.join(users)}")
        else:
            users = user_input.split()
    
    # 批量创建API Key
    created_keys = []
    for user in users:
        key_info = create_api_key(BASE_URL, ADMIN_TOKEN, user)
        if key_info:
            created_keys.append(key_info)
    
    # 总结
    print(f"\n📊 创建结果: 成功 {len(created_keys)}/{len(users)} 个API Key")
    
    if created_keys:
        print("\n📋 所有API Key汇总:")
        for key in created_keys:
            print(f"  {key['source_path']}: {key['key_value']}")
        
        # 生成测试命令
        print("\n🧪 测试命令示例:")
        for key in created_keys[:1]:  # 只显示第一个的测试命令
            print(f"""
curl -X POST "http://localhost:8514/proxy/miniai/v2/chat/completions" \\
  -H "X-API-Key: {key['key_value']}" \\
  -H "Content-Type: application/json" \\
  -d '{{
    "model": "gpt-3.5-turbo",
    "messages": [{{"role": "user", "content": "Hello!"}}],
    "max_tokens": 50
  }}'
""")

if __name__ == "__main__":
    main() 