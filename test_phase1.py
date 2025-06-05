#!/usr/bin/env python3
"""
M-FastGate Phase 1 交互式测试脚本

测试以下功能：
1. 基础框架功能
2. API Key 管理
3. 路由代理（需要模拟服务）
4. 审计日志
5. 统计功能
"""

import json
import time
import requests
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime
from typing import Optional, Dict, Any
import shutil
import os
from app.core.logging_config import get_logger, setup_logging

logger = get_logger(__name__)


class TestConfig:
    """测试配置"""
    BASE_URL = "http://localhost:8514"  # 根据你的实际端口
    ADMIN_TOKEN = "admin_secret_token_dev"
    MOCK_SERVER_PORT = 8512  # 改为8002避免冲突
    MOCK_SERVER_URL = f"http://localhost:{MOCK_SERVER_PORT}"
    
    def __init__(self):
        # 检测实际端口，先检测8514再检测8000
        try:
            response = requests.get("http://localhost:8514/health", timeout=2)
            if response.status_code == 200:
                self.BASE_URL = "http://localhost:8514"
                logger.info("Detected M-FastGate service running on http://localhost:8514")
                return
        except requests.exceptions.ConnectionError:
            logger.debug("M-FastGate service not found on http://localhost:8514")
        except Exception as e:
            logger.error(f"Error checking service on http://localhost:8514: {e}")
            
        try:
            response = requests.get("http://localhost:8000/health", timeout=2)
            if response.status_code == 200:
                self.BASE_URL = "http://localhost:8000"
                logger.info("Detected M-FastGate service running on http://localhost:8000")
        except requests.exceptions.ConnectionError:
            logger.debug("M-FastGate service not found on http://localhost:8000")
        except Exception as e:
            logger.error(f"Error checking service on http://localhost:8000: {e}")
        
        if self.BASE_URL == "http://localhost:8514": # Default value, means no service found
            logger.warning("M-FastGate service not detected on common ports (8514, 8000). Using default 8514.")


class MockServerHandler(BaseHTTPRequestHandler):
    """模拟目标服务器"""
    
    def log_message(self, format, *args):
        """静默日志"""
        pass
    
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        
        response_data = {
            "message": "Hello from mock server!",
            "path": self.path,
            "method": "GET",
            "timestamp": datetime.utcnow().isoformat(),
            "server": "mock-server"
        }
        self.wfile.write(json.dumps(response_data).encode())
    
    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)
        
        self.send_response(201)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        
        response_data = {
            "message": "Created successfully!",
            "path": self.path,
            "method": "POST",
            "received_data": post_data.decode() if post_data else None,
            "timestamp": datetime.utcnow().isoformat(),
            "server": "mock-server"
        }
        self.wfile.write(json.dumps(response_data).encode())
        
    def print_header(self, title: str):
        """打印标题"""
        logger.info("\n" + "=" * 60)
        logger.info(f"  {title}")
        logger.info("=" * 60)
    
    def print_step(self, step: str):
        """打印步骤"""
        logger.info(f"\n📋 {step}")
        logger.info("-" * 40)
    
    def print_result(self, success: bool, message: str, data: Any = None):
        """打印结果"""
        icon = "✅" if success else "❌"
        log_message = f"{icon} {message}"
        if data:
            log_message += f"\n   📄 响应数据: {json.dumps(data, ensure_ascii=False, indent=2)}"
        
        if success:
            logger.info(log_message)
        else:
            logger.error(log_message)
    
    def make_request(self, method: str, url: str, **kwargs) -> Optional[Dict]:
        """发送HTTP请求"""
        try:
            response = requests.request(method, url, timeout=10, **kwargs)
            
            if response.headers.get('content-type', '').startswith('application/json'):
                return {
                    "status_code": response.status_code,
                    "data": response.json(),
                    "headers": dict(response.headers)
                }
            else:
                return {
                    "status_code": response.status_code,
                    "data": {"content": response.text[:200] + "..." if len(response.text) > 200 else response.text},
                    "headers": dict(response.headers)
                }
        except Exception as e:
            return {
                "status_code": 0,
                "error": str(e)
            }
    
    def start_mock_server(self):
        """启动模拟服务器"""
        def run_server():
            self.mock_server = HTTPServer(('localhost', self.config.MOCK_SERVER_PORT), MockServerHandler)
            self.mock_server.serve_forever()
        
        self.mock_thread = threading.Thread(target=run_server, daemon=True)
        self.mock_thread.start()
        time.sleep(1)  # 等待服务器启动
        logger.info(f"🚀 模拟服务器已启动: {self.config.MOCK_SERVER_URL}")
    
    def stop_mock_server(self):
        """停止模拟服务器"""
        if self.mock_server:
            self.mock_server.shutdown()
            logger.info("🛑 模拟服务器已停止")
    
    def setup_test_routes(self):
        """设置测试路由配置"""
        # 备份原配置
        if os.path.exists("config/routes.yaml"):
            shutil.copy("config/routes.yaml", "config/routes_backup.yaml")
        
        # 创建测试配置
        test_routes = f"""routes:
  - name: "测试示例服务"
    path_prefix: "/api/v1/example"
    targets:
      - url: "http://localhost:{self.config.MOCK_SERVER_PORT}"
        timeout: 30
    auth_required: true
"""
        with open("config/routes.yaml", "w", encoding="utf-8") as f:
            f.write(test_routes)
        
        print(f"🔧 已设置测试路由配置，目标: localhost:{self.config.MOCK_SERVER_PORT}")
    
    def restore_routes(self):
        """恢复原路由配置"""
        if os.path.exists("config/routes_backup.yaml"):
            shutil.move("config/routes_backup.yaml", "config/routes.yaml")
            print("🔧 已恢复原路由配置")
    
    def restart_service_if_needed(self):
        """如果需要，重启服务以加载新配置"""
        print("⚠️  注意：路由配置已更改，可能需要重启服务以生效")
        print("   如果代理测试失败，请手动重启服务: python -m app.main")
    
    def test_basic_framework(self):
        """测试基础框架功能"""
        self.print_header("测试 1: 基础框架功能")
        
        # 测试健康检查
        self.print_step("1.1 测试健康检查接口")
        result = self.make_request("GET", f"{self.config.BASE_URL}/health")
        if result and result["status_code"] == 200:
            self.print_result(True, "健康检查成功", result["data"])
        else:
            self.print_result(False, "健康检查失败", result)
        
        # 测试根路径
        self.print_step("1.2 测试根路径接口")
        result = self.make_request("GET", f"{self.config.BASE_URL}/")
        if result and result["status_code"] == 200:
            self.print_result(True, "根路径访问成功", result["data"])
        else:
            self.print_result(False, "根路径访问失败", result)
        
        # 测试API文档
        self.print_step("1.3 测试API文档接口")
        result = self.make_request("GET", f"{self.config.BASE_URL}/docs")
        if result and result["status_code"] == 200:
            self.print_result(True, "API文档访问成功")
        else:
            self.print_result(False, "API文档访问失败", result)
    
    def test_api_key_management(self):
        """测试API Key管理功能"""
        self.print_header("测试 2: API Key 管理功能")
        
        # 2.1 创建API Key
        self.print_step("2.1 创建API Key")
        create_data = {
            "source_path": "test_app",
            "permissions": ["read", "write"],
            "expires_days": 30,
            "rate_limit": 100
        }
        
        result = self.make_request(
            "POST", 
            f"{self.config.BASE_URL}/admin/keys?token={self.config.ADMIN_TOKEN}",
            json=create_data
        )
        
        if result and result["status_code"] == 200:
            api_key_data = result["data"]
            self.created_keys.append(api_key_data["key_id"])
            self.print_result(True, "API Key创建成功", api_key_data)
            
            # 保存API Key用于后续测试
            self.test_api_key = api_key_data["key_value"]
            self.test_key_id = api_key_data["key_id"]
        else:
            self.print_result(False, "API Key创建失败", result)
            return
        
        # 2.2 查询API Key列表
        self.print_step("2.2 查询API Key列表")
        result = self.make_request(
            "GET", 
            f"{self.config.BASE_URL}/admin/keys?token={self.config.ADMIN_TOKEN}"
        )
        
        if result and result["status_code"] == 200:
            self.print_result(True, f"查询到 {len(result['data'])} 个API Key", result["data"])
        else:
            self.print_result(False, "API Key列表查询失败", result)
        
        # 2.3 查询单个API Key
        self.print_step("2.3 查询单个API Key详情")
        result = self.make_request(
            "GET", 
            f"{self.config.BASE_URL}/admin/keys/{self.test_key_id}?token={self.config.ADMIN_TOKEN}"
        )
        
        if result and result["status_code"] == 200:
            self.print_result(True, "API Key详情查询成功", result["data"])
        else:
            self.print_result(False, "API Key详情查询失败", result)
        
        # 2.4 更新API Key
        self.print_step("2.4 更新API Key")
        update_data = {
            "permissions": ["read"],
            "rate_limit": 50
        }
        
        result = self.make_request(
            "PUT", 
            f"{self.config.BASE_URL}/admin/keys/{self.test_key_id}?token={self.config.ADMIN_TOKEN}",
            json=update_data
        )
        
        if result and result["status_code"] == 200:
            self.print_result(True, "API Key更新成功", result["data"])
        else:
            self.print_result(False, "API Key更新失败", result)
    
    def test_proxy_functionality(self):
        """测试代理转发功能"""
        self.print_header("测试 3: 路由代理功能")
        
        if not hasattr(self, 'test_api_key'):
            self.print_result(False, "需要先创建API Key")
            return
        
        # 启动模拟服务器
        self.start_mock_server()
        
        # 3.1 测试GET请求代理
        self.print_step("3.1 测试GET请求代理转发")
        headers = {
            "X-API-Key": self.test_api_key,
            "X-Source-Path": "test_app"
        }
        
        result = self.make_request(
            "GET", 
            f"{self.config.BASE_URL}/api/v1/example/users",
            headers=headers
        )
        
        if result and result["status_code"] == 200:
            self.print_result(True, "GET代理转发成功", result["data"])
        else:
            self.print_result(False, "GET代理转发失败", result)
        
        # 3.2 测试POST请求代理
        self.print_step("3.2 测试POST请求代理转发")
        post_data = {"name": "Test User", "email": "test@example.com"}
        
        result = self.make_request(
            "POST", 
            f"{self.config.BASE_URL}/api/v1/example/users",
            headers=headers,
            json=post_data
        )
        
        if result and result["status_code"] == 201:
            self.print_result(True, "POST代理转发成功", result["data"])
        else:
            self.print_result(False, "POST代理转发失败", result)
        
        # 3.3 测试Authorization Bearer认证
        self.print_step("3.3 测试Authorization Bearer认证")
        auth_headers = {
            "Authorization": f"Bearer {self.test_api_key}",
            "X-Source-Path": "test_app"
        }
        
        result = self.make_request(
            "GET", 
            f"{self.config.BASE_URL}/api/v1/example/profile",
            headers=auth_headers
        )
        
        if result and result["status_code"] == 200:
            self.print_result(True, "Bearer认证代理转发成功", result["data"])
        else:
            self.print_result(False, "Bearer认证代理转发失败", result)
        
        # 3.4 测试未认证请求
        self.print_step("3.4 测试未认证请求（应该失败）")
        result = self.make_request(
            "GET", 
            f"{self.config.BASE_URL}/api/v1/example/test"
        )
        
        if result and result["status_code"] == 401:
            self.print_result(True, "未认证请求正确被拒绝", result["data"])
        else:
            self.print_result(False, "未认证请求处理异常", result)
        
        # 3.5 测试无效路径
        self.print_step("3.5 测试无效路径（应该404）")
        result = self.make_request(
            "GET", 
            f"{self.config.BASE_URL}/invalid/path/test",
            headers=headers
        )
        
        if result and result["status_code"] == 404:
            self.print_result(True, "无效路径正确返回404", result["data"])
        else:
            self.print_result(False, "无效路径处理异常", result)
    
    def test_audit_logging(self):
        """测试审计日志功能"""
        self.print_header("测试 4: 审计日志功能")
        
        # 等待日志记录
        time.sleep(1)
        
        # 4.1 查询审计日志
        self.print_step("4.1 查询审计日志")
        result = self.make_request(
            "GET", 
            f"{self.config.BASE_URL}/admin/logs?token={self.config.ADMIN_TOKEN}&limit=5"
        )
        
        if result and result["status_code"] == 200:
            logs = result["data"]
            self.print_result(True, f"查询到 {len(logs)} 条审计日志", {"logs_count": len(logs)})
            if logs:
                print(f"   📋 最新日志示例:")
                latest_log = logs[0]
                for key, value in latest_log.items():
                    print(f"      {key}: {value}")
        else:
            self.print_result(False, "审计日志查询失败", result)
        
        # 4.2 查询特定API Key的日志
        if hasattr(self, 'test_api_key'):
            self.print_step("4.2 查询特定API Key的日志")
            result = self.make_request(
                "GET", 
                f"{self.config.BASE_URL}/admin/logs?token={self.config.ADMIN_TOKEN}&api_key={self.test_api_key}&limit=3"
            )
            
            if result and result["status_code"] == 200:
                logs = result["data"]
                self.print_result(True, f"查询到该API Key的 {len(logs)} 条日志")
            else:
                self.print_result(False, "特定API Key日志查询失败", result)
    
    def test_metrics_and_statistics(self):
        """测试统计功能"""
        self.print_header("测试 5: 统计指标功能")
        
        # 5.1 获取统计指标
        self.print_step("5.1 获取整体统计指标")
        result = self.make_request(
            "GET", 
            f"{self.config.BASE_URL}/admin/metrics?token={self.config.ADMIN_TOKEN}"
        )
        
        if result and result["status_code"] == 200:
            metrics = result["data"]
            self.print_result(True, "统计指标获取成功", metrics)
        else:
            self.print_result(False, "统计指标获取失败", result)
        
        # 5.2 获取路由配置
        self.print_step("5.2 获取路由配置")
        result = self.make_request(
            "GET", 
            f"{self.config.BASE_URL}/admin/routes?token={self.config.ADMIN_TOKEN}"
        )
        
        if result and result["status_code"] == 200:
            routes = result["data"]
            self.print_result(True, "路由配置获取成功", routes)
        else:
            self.print_result(False, "路由配置获取失败", result)
    
    def cleanup(self):
        """清理测试数据"""
        self.print_header("清理测试数据")
        
        # 删除创建的API Key
        for key_id in self.created_keys:
            self.print_step(f"删除API Key: {key_id}")
            result = self.make_request(
                "DELETE", 
                f"{self.config.BASE_URL}/admin/keys/{key_id}?token={self.config.ADMIN_TOKEN}"
            )
            
            if result and result["status_code"] == 200:
                self.print_result(True, "API Key删除成功")
            else:
                self.print_result(False, "API Key删除失败", result)
        
        # 停止模拟服务器
        self.stop_mock_server()
    
    def run_all_tests(self):
        """运行所有测试"""
        print("🧪 M-FastGate Phase 1 功能测试")
        print(f"🔗 测试目标: {self.config.BASE_URL}")
        print(f"⏰ 开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        try:
            # 设置测试路由配置
            self.setup_test_routes()
            self.restart_service_if_needed()
            
            self.test_basic_framework()
            self.test_api_key_management()
            self.test_proxy_functionality()
            self.test_audit_logging()
            self.test_metrics_and_statistics()
        
        except KeyboardInterrupt:
            print("\n\n⚠️  测试被用户中断")
        except Exception as e:
            print(f"\n\n❌ 测试过程中发生错误: {e}")
        
        finally:
            self.cleanup()
            self.restore_routes()
        
        print(f"\n\n🏁 测试完成: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    def run_interactive_tests(self):
        """运行交互式测试"""
        while True:
            print("\n" + "="*60)
            print("🧪 M-FastGate Phase 1 交互式测试")
            print("="*60)
            print("1. 测试基础框架功能")
            print("2. 测试API Key管理")
            print("3. 测试路由代理功能")
            print("4. 测试审计日志功能") 
            print("5. 测试统计指标功能")
            print("6. 运行完整测试")
            print("7. 清理测试数据")
            print("0. 退出")
            
            choice = input("\n请选择要执行的测试 (0-7): ").strip()
            
            try:
                if choice == "0":
                    break
                elif choice == "1":
                    self.test_basic_framework()
                elif choice == "2":
                    self.test_api_key_management()
                elif choice == "3":
                    self.test_proxy_functionality()
                elif choice == "4":
                    self.test_audit_logging()
                elif choice == "5":
                    self.test_metrics_and_statistics()
                elif choice == "6":
                    self.run_all_tests()
                    break
                elif choice == "7":
                    self.cleanup()
                else:
                    print("❌ 无效选择，请重新输入")
                    continue
                    
                input("\n按回车键继续...")
                
            except KeyboardInterrupt:
                print("\n\n⚠️  操作被用户中断")
                break
            except Exception as e:
                print(f"\n\n❌ 执行过程中发生错误: {e}")
                input("\n按回车键继续...")


def main():
    """主函数"""
    tester = Phase1Tester()
    
    print("欢迎使用 M-FastGate Phase 1 测试工具!")
    print("\n选择测试模式:")
    print("1. 交互式测试 (推荐)")
    print("2. 运行完整测试")
    
    mode = input("\n请选择模式 (1-2): ").strip()
    
    if mode == "1":
        tester.run_interactive_tests()
    elif mode == "2":
        tester.run_all_tests()
    else:
        print("❌ 无效选择")
        return
    
    print("\n👋 感谢使用测试工具!")


if __name__ == "__main__":
    main() 