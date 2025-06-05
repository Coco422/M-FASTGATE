#!/usr/bin/env python3
"""
数据库初始化脚本
用于在新环境中创建表和插入初始数据
"""

import sqlite3
import os
import sys
from datetime import datetime

def get_database_path():
    """获取数据库路径"""
    # 检查多个可能的数据库路径
    possible_paths = [
        "app/data/fastgate.db",
        "data/fastgate.db",
        "./fastgate.db"
    ]
    
    for path in possible_paths:
        # 检查目录是否存在，如果不存在则创建
        db_dir = os.path.dirname(path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
        return path
    
    return "fastgate.db"

def execute_sql_file(cursor, file_path):
    """执行SQL文件"""
    if not os.path.exists(file_path):
        print(f"❌ SQL文件不存在: {file_path}")
        return False
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            sql_content = f.read()
        
        # 分割SQL语句并执行
        statements = sql_content.split(';')
        for statement in statements:
            statement = statement.strip()
            if statement:
                cursor.execute(statement)
        
        print(f"✅ 成功执行SQL文件: {file_path}")
        return True
    except Exception as e:
        print(f"❌ 执行SQL文件失败 {file_path}: {e}")
        return False

def insert_default_model_routes(cursor):
    """插入默认模型路由配置"""
    print("🔄 插入默认模型路由配置...")
    
    model_routes = [
        {
            'id': 'route_deepseekr1',
            'model_name': 'DeepSeekR1',
            'endpoint_type': 'chat',
            'proxy_path': '/**',
            'parameters': '{"max_concurrency": 100, "context_length": "32K/8K", "recommended_temperature": 0.6, "recommended_top_p": 0.95}',
            'is_active': 1
        },
        {
            'id': 'route_qwq32b',
            'model_name': 'QwQ-32B',
            'endpoint_type': 'chat',
            'proxy_path': '/**',
            'parameters': '{"max_concurrency": 100, "context_length": "120K/8K"}',
            'is_active': 1
        },
        {
            'id': 'route_qwen25_32b',
            'model_name': 'Qwen2.5-32B-Instruct',
            'endpoint_type': 'chat',
            'proxy_path': '/**',
            'parameters': '{"max_concurrency": 100, "context_length": "120K/8K"}',
            'is_active': 1
        },
        {
            'id': 'route_bge_large_zh',
            'model_name': 'bge-large-zh-v1.5',
            'endpoint_type': 'embedding',
            'proxy_path': '/embed',
            'parameters': '{"max_input_tokens": 512, "output_dimensions": 1024, "embedding_type": "text"}',
            'is_active': 1
        }
    ]
    
    insert_sql = """
    INSERT OR IGNORE INTO model_routes 
    (id, model_name, endpoint_type, proxy_path, parameters, is_active, health_check_path, timeout, max_retries, health_status, created_at, updated_at) 
    VALUES (?, ?, ?, ?, ?, ?, '/health', 30, 3, 'unknown', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
    """
    
    success_count = 0
    for route in model_routes:
        try:
            cursor.execute(insert_sql, (
                route['id'],
                route['model_name'],
                route['endpoint_type'],
                route['proxy_path'],
                route['parameters'],
                route['is_active']
            ))
            success_count += 1
            print(f"  ✅ {route['model_name']} ({route['endpoint_type']})")
        except Exception as e:
            print(f"  ❌ {route['model_name']}: {e}")
    
    print(f"📊 成功插入 {success_count}/{len(model_routes)} 个模型路由配置")
    return success_count > 0

def check_existing_data(cursor):
    """检查现有数据"""
    print("🔍 检查现有数据...")
    
    try:
        # 检查模型路由表
        cursor.execute("SELECT COUNT(*) FROM model_routes WHERE is_active = 1")
        active_routes = cursor.fetchone()[0]
        print(f"  📈 活跃模型路由: {active_routes} 个")
        
        # 检查API Key表
        cursor.execute("SELECT COUNT(*) FROM api_keys WHERE is_active = 1")
        active_keys = cursor.fetchone()[0]
        print(f"  🔑 活跃API Key: {active_keys} 个")
        
        # 检查审计日志表
        cursor.execute("SELECT COUNT(*) FROM audit_logs")
        audit_count = cursor.fetchone()[0]
        print(f"  📋 审计日志记录: {audit_count} 条")
        
        return {
            'active_routes': active_routes,
            'active_keys': active_keys,
            'audit_count': audit_count
        }
    except Exception as e:
        print(f"  ❌ 检查数据失败: {e}")
        return None

def main():
    """主函数"""
    print("🚀 开始数据库初始化...")
    print("=" * 60)
    
    # 获取数据库路径
    db_path = get_database_path()
    print(f"📂 数据库路径: {db_path}")
    
    try:
        # 连接数据库
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        print("✅ 数据库连接成功")
        
        # 执行migrations文件
        migrations_file = "migrations/phase2_4_model_routes.sql"
        if os.path.exists(migrations_file):
            execute_sql_file(cursor, migrations_file)
        else:
            print(f"⚠️  Migration文件不存在: {migrations_file}")
            print("🔄 手动创建表和插入数据...")
            
            # 手动插入模型路由配置
            insert_default_model_routes(cursor)
        
        # 提交事务
        conn.commit()
        print("✅ 数据库事务已提交")
        
        # 检查数据
        print("\n" + "=" * 60)
        stats = check_existing_data(cursor)
        
        if stats and stats['active_routes'] == 0:
            print("\n⚠️  检测到没有活跃的模型路由配置，重新插入...")
            insert_default_model_routes(cursor)
            conn.commit()
            check_existing_data(cursor)
        
        print("\n" + "=" * 60)
        print("🎉 数据库初始化完成！")
        
    except Exception as e:
        print(f"❌ 数据库初始化失败: {e}")
        sys.exit(1)
    finally:
        if 'conn' in locals():
            conn.close()
            print("📪 数据库连接已关闭")

if __name__ == "__main__":
    main() 