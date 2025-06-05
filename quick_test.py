#!/usr/bin/env python3
"""
M-FastGate 快速测试脚本
测试基础功能，不需要模拟服务器
"""

import requests
import json
from datetime import datetime


def test_basic_features():
    """测试基础功能"""
    
    base_url = "http://localhost:8514"
    admin_token = "admin_secret_token_dev"
    
    print("🧪 M-FastGate 快速功能测试")
    print(f"🔗 测试目标: {base_url}")
    print(f"⏰ 开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 1. 测试健康检查
    print("\n📋 1. 测试健康检查")
    try:
        response = requests.get(f"{base_url}/health", timeout=5)
        print(f"✅ 健康检查成功: {response.status_code}")
        print(f"   响应: {response.json()}")
    except Exception as e:
        print(f"❌ 健康检查失败: {e}")
        return
    
    # 2. 测试根路径
    print("\n📋 2. 测试根路径")
    try:
        response = requests.get(f"{base_url}/", timeout=5)
        print(f"✅ 根路径成功: {response.status_code}")
        print(f"   响应: {response.json()}")
    except Exception as e:
        print(f"❌ 根路径失败: {e}")
    
    # 3. 创建API Key
    print("\n📋 3. 创建API Key")
    try:
        create_data = {
            "source_path": "test_app",
            "permissions": ["read", "write"],
            "expires_days": 30
        }
        response = requests.post(
            f"{base_url}/admin/keys?token={admin_token}",
            json=create_data,
            timeout=5
        )
        print(f"✅ API Key创建成功: {response.status_code}")
        api_key_data = response.json()
        print(f"   Key ID: {api_key_data['key_id']}")
        print(f"   Key Value: {api_key_data['key_value'][:20]}...")
        
        # 保存用于后续测试
        api_key = api_key_data['key_value']
        key_id = api_key_data['key_id']
        
    except Exception as e:
        print(f"❌ API Key创建失败: {e}")
        return
    
    # 4. 查询API Key列表
    print("\n📋 4. 查询API Key列表")
    try:
        response = requests.get(f"{base_url}/admin/keys?token={admin_token}", timeout=5)
        print(f"✅ API Key列表查询成功: {response.status_code}")
        keys = response.json()
        print(f"   找到 {len(keys)} 个API Key")
    except Exception as e:
        print(f"❌ API Key列表查询失败: {e}")
    
    # 5. 测试未认证的代理请求（应该失败）
    print("\n📋 5. 测试未认证代理请求")
    try:
        response = requests.get(f"{base_url}/api/v1/example/test", timeout=5)
        if response.status_code == 401:
            print(f"✅ 未认证请求正确被拒绝: {response.status_code}")
        else:
            print(f"⚠️  未认证请求返回异常状态: {response.status_code}")
    except Exception as e:
        print(f"❌ 未认证请求测试失败: {e}")
    
    # 6. 查询审计日志
    print("\n📋 6. 查询审计日志")
    try:
        response = requests.get(f"{base_url}/admin/logs?token={admin_token}&limit=3", timeout=5)
        print(f"✅ 审计日志查询成功: {response.status_code}")
        logs = response.json()
        print(f"   找到 {len(logs)} 条日志")
        if logs:
            print(f"   最新日志: {logs[0]['method']} {logs[0]['path']}")
    except Exception as e:
        print(f"❌ 审计日志查询失败: {e}")
    
    # 7. 获取统计指标
    print("\n📋 7. 获取统计指标")
    try:
        response = requests.get(f"{base_url}/admin/metrics?token={admin_token}", timeout=5)
        print(f"✅ 统计指标获取成功: {response.status_code}")
        metrics = response.json()
        print(f"   API Key总数: {metrics.get('total_keys', 'N/A')}")
        print(f"   总请求数: {metrics.get('total_requests', 'N/A')}")
    except Exception as e:
        print(f"❌ 统计指标获取失败: {e}")
    
    # 8. 清理：删除创建的API Key
    print("\n📋 8. 清理测试数据")
    try:
        response = requests.delete(f"{base_url}/admin/keys/{key_id}?token={admin_token}", timeout=5)
        print(f"✅ API Key删除成功: {response.status_code}")
    except Exception as e:
        print(f"❌ API Key删除失败: {e}")
    
    print(f"\n🏁 测试完成: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    test_basic_features() 