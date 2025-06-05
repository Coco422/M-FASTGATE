 #!/usr/bin/env python3
"""
API网关功能测试脚本

测试场景：
1. 多个用户(key1, key2, key3)请求统一端点
2. 验证异步审计日志记录
3. 验证参数清洗和转发
4. 验证流式和非流式响应
"""

import asyncio
import httpx
import json
import time
from datetime import datetime


class GatewayTester:
    """API网关测试器"""
    
    def __init__(self, base_url="http://localhost:8514"):
        self.base_url = base_url
        self.admin_token = "admin_secret_token_dev"
        self.test_keys = []
    
    async def setup_test_keys(self):
        """创建测试用的API Keys"""
        async with httpx.AsyncClient() as client:
            for i in range(1, 4):  # key1, key2, key3
                key_data = {
                    "source_path": f"user{i}",
                    "permissions": ["chat"],
                    "expires_days": 30
                }
                
                response = await client.post(
                    f"{self.base_url}/admin/keys?token={self.admin_token}",
                    json=key_data
                )
                
                if response.status_code == 200:
                    key_info = response.json()
                    self.test_keys.append({
                        "user": f"user{i}",
                        "key_id": key_info["key_id"],
                        "key_value": key_info["key_value"]
                    })
                    print(f"✅ Created API Key for user{i}: {key_info['key_value'][:20]}...")
                else:
                    print(f"❌ Failed to create API Key for user{i}: {response.text}")
    
    async def test_chat_completions(self, api_key, stream=False):
        """测试聊天完成请求"""
        headers = {
            "X-API-Key": api_key,
            "Content-Type": "application/json"
        }
        
        data = {
            "model": "gpt-3.5-turbo",
            "messages": [
                {"role": "user", "content": "Hello, this is a test message."}
            ],
            "stream": stream,
            "max_tokens": 50
        }
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                if stream:
                    # 流式请求测试
                    async with client.stream(
                        "POST",
                        f"{self.base_url}/proxy/miniai/v2/chat/completions",
                        headers=headers,
                        json=data
                    ) as response:
                        if response.status_code == 200:
                            chunks = 0
                            async for chunk in response.aiter_bytes():
                                chunks += 1
                                if chunks >= 3:  # 只读取前几个chunk
                                    break
                            return {"status": "success", "type": "stream", "chunks": chunks}
                        else:
                            return {"status": "error", "code": response.status_code, "text": response.text}
                else:
                    # 普通请求测试
                    response = await client.post(
                        f"{self.base_url}/proxy/miniai/v2/chat/completions",
                        headers=headers,
                        json=data
                    )
                    
                    if response.status_code == 200:
                        return {"status": "success", "type": "normal", "response_size": len(response.content)}
                    else:
                        return {"status": "error", "code": response.status_code, "text": response.text}
        
        except Exception as e:
            return {"status": "error", "exception": str(e)}
    
    async def check_audit_logs(self):
        """检查审计日志"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/admin/logs?token={self.admin_token}&limit=20"
            )
            
            if response.status_code == 200:
                logs = response.json()
                return logs
            else:
                print(f"❌ Failed to get audit logs: {response.text}")
                return []
    
    async def run_concurrent_tests(self):
        """运行并发测试"""
        print("\n🚀 Starting concurrent gateway tests...")
        
        # 创建并发任务
        tasks = []
        for key_info in self.test_keys:
            # 每个用户发送一个普通请求和一个流式请求
            tasks.append(self.test_chat_completions(key_info["key_value"], stream=False))
            tasks.append(self.test_chat_completions(key_info["key_value"], stream=True))
        
        # 执行并发请求
        start_time = time.time()
        results = await asyncio.gather(*tasks, return_exceptions=True)
        end_time = time.time()
        
        # 分析结果
        success_count = 0
        error_count = 0
        stream_count = 0
        normal_count = 0
        
        for i, result in enumerate(results):
            user_idx = i // 2
            request_type = "stream" if i % 2 == 1 else "normal"
            user = self.test_keys[user_idx]["user"]
            
            if isinstance(result, dict) and result.get("status") == "success":
                success_count += 1
                if result.get("type") == "stream":
                    stream_count += 1
                else:
                    normal_count += 1
                print(f"✅ {user} {request_type} request: {result}")
            else:
                error_count += 1
                print(f"❌ {user} {request_type} request failed: {result}")
        
        print(f"\n📊 Test Results:")
        print(f"   Total requests: {len(results)}")
        print(f"   Successful: {success_count}")
        print(f"   Failed: {error_count}")
        print(f"   Stream requests: {stream_count}")
        print(f"   Normal requests: {normal_count}")
        print(f"   Total time: {end_time - start_time:.2f}s")
        
        return success_count, error_count
    
    async def validate_audit_logs(self):
        """验证审计日志"""
        print("\n📋 Checking audit logs...")
        
        # 等待一下让异步日志写入完成
        await asyncio.sleep(2)
        
        logs = await self.check_audit_logs()
        if not logs:
            print("❌ No audit logs found")
            return False
        
        print(f"✅ Found {len(logs)} audit log entries")
        
        # 检查最近的日志
        recent_logs = [log for log in logs if log.get("path") == "/proxy/miniai/v2/chat/completions"]
        
        print(f"✅ Found {len(recent_logs)} gateway-related logs")
        
        # 检查流式和普通请求的日志
        stream_logs = [log for log in recent_logs if log.get("is_stream")]
        normal_logs = [log for log in recent_logs if not log.get("is_stream")]
        
        print(f"   Stream requests logged: {len(stream_logs)}")
        print(f"   Normal requests logged: {len(normal_logs)}")
        
        # 显示最新的几条日志
        print("\n📄 Recent audit logs:")
        for log in recent_logs[:3]:
            print(f"   - {log.get('created_at')} | {log.get('api_key', 'N/A')[:10]}... | "
                  f"{log.get('status_code')} | {log.get('response_time_ms')}ms | "
                  f"Stream: {log.get('is_stream', False)}")
        
        return len(recent_logs) > 0
    
    async def cleanup_test_keys(self):
        """清理测试Key"""
        print("\n🧹 Cleaning up test keys...")
        
        async with httpx.AsyncClient() as client:
            for key_info in self.test_keys:
                response = await client.delete(
                    f"{self.base_url}/admin/keys/{key_info['key_id']}?token={self.admin_token}"
                )
                
                if response.status_code == 200:
                    print(f"✅ Deleted key for {key_info['user']}")
                else:
                    print(f"❌ Failed to delete key for {key_info['user']}")
    
    async def run_full_test(self):
        """运行完整测试"""
        print("🎯 M-FastGate API Gateway Test Suite")
        print("=" * 50)
        
        try:
            # 1. 设置测试Keys
            await self.setup_test_keys()
            if not self.test_keys:
                print("❌ Failed to create test keys, aborting")
                return
            
            # 2. 运行并发测试
            success_count, error_count = await self.run_concurrent_tests()
            
            # 3. 验证审计日志
            logs_ok = await self.validate_audit_logs()
            
            # 4. 总结测试结果
            print("\n" + "=" * 50)
            print("🎯 Test Summary:")
            print(f"   API Keys created: {len(self.test_keys)}")
            print(f"   Successful requests: {success_count}")
            print(f"   Failed requests: {error_count}")
            print(f"   Audit logging: {'✅ Working' if logs_ok else '❌ Failed'}")
            
            if success_count > 0 and logs_ok:
                print("\n🎉 API Gateway test PASSED!")
            else:
                print("\n❌ API Gateway test FAILED!")
        
        finally:
            # 5. 清理
            await self.cleanup_test_keys()


async def main():
    """主函数"""
    # 检查服务是否运行
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get("http://localhost:8514/health")
            if response.status_code != 200:
                print("❌ M-FastGate service is not running. Please start it first.")
                return
            print("✅ M-FastGate service is running")
    except:
        print("❌ Cannot connect to M-FastGate service. Please start it first.")
        return
    
    # 运行测试
    tester = GatewayTester()
    await tester.run_full_test()


if __name__ == "__main__":
    asyncio.run(main())