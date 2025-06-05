#!/usr/bin/env python3
"""
M-FastGate v0.2.0 数据库初始化脚本
用于创建和维护v0.2.0版本的数据库结构
"""

import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker

# 中国时区
CHINA_TZ = timezone(timedelta(hours=8))

def get_china_time():
    """获取中国时间"""
    return datetime.now(CHINA_TZ)

class DatabaseInitializer:
    """数据库初始化器"""
    
    def __init__(self, database_url: str):
        self.database_url = database_url
        
        # 从SQLite URL中提取文件路径
        if database_url.startswith("sqlite:///"):
            self.db_path = database_url[10:]  # 移除 sqlite:/// 前缀
            # 确保数据目录存在
            db_dir = os.path.dirname(self.db_path)
            if db_dir:
                os.makedirs(db_dir, exist_ok=True)
        
        # 创建数据库引擎
        self.engine = create_engine(
            database_url,
            echo=False,
            connect_args={"check_same_thread": False} if "sqlite" in database_url else {}
        )
        
        # 创建会话工厂
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
    
    def ensure_database(self):
        """确保数据库结构正确"""
        print("🚀 M-FastGate v0.2.0 数据库初始化器启动")
        print("=" * 60)
        print(f"📂 数据库URL: {self.database_url}")
        
        try:
            # 检查数据库文件是否存在
            if hasattr(self, 'db_path') and not os.path.exists(self.db_path):
                print("📦 数据库文件不存在，创建新数据库...")
                self.create_database()
            else:
                print("🔍 检查现有数据库结构...")
                if self.validate_schema():
                    print("✅ 数据库结构验证通过")
                else:
                    print("⚠️  数据库结构不匹配，重新创建...")
                    self.recreate_database()
                    
            print("✅ 数据库初始化完成")
            
        except Exception as e:
            print(f"❌ 数据库初始化失败: {e}")
            raise
    
    def create_database(self):
        """创建新数据库"""
        self.create_tables()
        self.insert_default_data()
        print("✅ 新数据库创建成功")
    
    def recreate_database(self):
        """重新创建数据库"""
        # 备份旧数据库文件（如果是SQLite）
        if hasattr(self, 'db_path') and os.path.exists(self.db_path):
            backup_path = f"{self.db_path}.backup.{int(datetime.now().timestamp())}"
            os.rename(self.db_path, backup_path)
            print(f"📦 旧数据库已备份到: {backup_path}")
        
        self.create_database()
    
    def create_tables(self):
        """创建v0.2.0表结构"""
        print("🔨 创建数据库表...")
    
        with self.engine.connect() as conn:
            # 1. api_keys表
            conn.execute(text("""
            CREATE TABLE IF NOT EXISTS api_keys (
                key_id VARCHAR(50) PRIMARY KEY,
                key_value VARCHAR(100) UNIQUE NOT NULL,
                source_path VARCHAR(100) NOT NULL,
                permissions TEXT DEFAULT '[]',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                expires_at DATETIME,
                is_active BOOLEAN DEFAULT TRUE,
                usage_count INTEGER DEFAULT 0,
                rate_limit INTEGER,
                last_used_at DATETIME
            )
            """))
            print("  ✅ api_keys表创建成功")
        
            # 2. audit_logs表 
            conn.execute(text("""
            CREATE TABLE IF NOT EXISTS audit_logs (
                id VARCHAR(50) PRIMARY KEY,
                request_id VARCHAR(50) NOT NULL,
                api_key VARCHAR(100),
                source_path VARCHAR(100),
                method VARCHAR(10) NOT NULL,
                path VARCHAR(500) NOT NULL,
                target_url VARCHAR(500),
                status_code INTEGER,
                request_time DATETIME NOT NULL,
                first_response_time DATETIME,
                response_time DATETIME,
                response_time_ms INTEGER,
                request_size INTEGER DEFAULT 0,
                response_size INTEGER DEFAULT 0,
                user_agent VARCHAR(500),
                ip_address VARCHAR(50),
                is_stream BOOLEAN DEFAULT FALSE,
                stream_chunks INTEGER DEFAULT 0,
                error_message TEXT,
                request_headers TEXT,
                request_body TEXT,
                response_headers TEXT,
                response_body TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """))
            print("  ✅ audit_logs表创建成功")
            
            # 3. proxy_routes表
            conn.execute(text("""
            CREATE TABLE IF NOT EXISTS proxy_routes (
                route_id VARCHAR(50) PRIMARY KEY,
                route_name VARCHAR(100) NOT NULL,
                description TEXT,
                match_path VARCHAR(500) NOT NULL,
                match_method VARCHAR(20) DEFAULT 'ANY',
                match_headers TEXT,
                match_body_schema TEXT,
                target_host VARCHAR(200) NOT NULL,
                target_path VARCHAR(500) NOT NULL,
                target_protocol VARCHAR(10) DEFAULT 'http',
                strip_path_prefix BOOLEAN DEFAULT FALSE,
                add_headers TEXT,
                add_body_fields TEXT,
                remove_headers TEXT,
                timeout INTEGER DEFAULT 30,
                retry_count INTEGER DEFAULT 0,
                is_active BOOLEAN DEFAULT TRUE,
                priority INTEGER DEFAULT 100,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """))
            print("  ✅ proxy_routes表创建成功")
            
            # 创建索引
            self.create_indexes(conn)
        
        # 提交事务
        conn.commit()
    
    def create_indexes(self, conn):
        """创建索引"""
        print("📊 创建数据库索引...")
        
        # audit_logs索引
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_audit_logs_request_time ON audit_logs(request_time)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_audit_logs_api_key ON audit_logs(api_key)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_audit_logs_path ON audit_logs(path)"))
        
        # proxy_routes索引
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_proxy_routes_match_path ON proxy_routes(match_path)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_proxy_routes_priority ON proxy_routes(priority)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_proxy_routes_is_active ON proxy_routes(is_active)"))
        
        print("  ✅ 索引创建成功")
    
    def insert_default_data(self):
        """插入默认数据"""
        print("📦 插入默认数据...")
        
        with self.engine.connect() as conn:
            # 插入默认API Key
            conn.execute(text("""
            INSERT OR IGNORE INTO api_keys 
            (key_id, key_value, source_path, permissions, created_at, is_active)
            VALUES (:key_id, :key_value, :source_path, :permissions, :created_at, :is_active)
            """), {
                'key_id': 'default_key_001',
                'key_value': 'fg_default_development_key',
                'source_path': '/default',
                'permissions': '["read", "write"]',
                'created_at': get_china_time().isoformat(),
                'is_active': True
            })
            print("  ✅ 默认API Key插入成功")
            
            # 插入示例代理路由
            conn.execute(text("""
            INSERT OR IGNORE INTO proxy_routes 
            (route_id, route_name, description, match_path, match_method, 
             target_host, target_path, target_protocol, is_active, priority, created_at, updated_at)
            VALUES (:route_id, :route_name, :description, :match_path, :match_method,
                    :target_host, :target_path, :target_protocol, :is_active, :priority, :created_at, :updated_at)
            """), {
                'route_id': 'example_route_001',
                'route_name': '示例代理路由',
                'description': '示例代理到本地服务',
                'match_path': '/api/v1/*',
                'match_method': 'ANY',
                'target_host': 'localhost:8001',
                'target_path': '/v1/',
                'target_protocol': 'http',
                'is_active': False,  # 默认不激活
                'priority': 100,
                'created_at': get_china_time().isoformat(),
                'updated_at': get_china_time().isoformat()
            })
            print("  ✅ 示例代理路由插入成功")
            
            # 提交事务
            conn.commit()
    
    def validate_schema(self):
        """验证数据库结构"""
        try:
            inspector = inspect(self.engine)
            
            # 检查必要的表是否存在
            required_tables = ['api_keys', 'audit_logs', 'proxy_routes']
            existing_tables = inspector.get_table_names()
            
            for table in required_tables:
                if table not in existing_tables:
                    print(f"  ❌ 缺少表: {table}")
                    return False
            
            # 检查audit_logs表结构（关键字段）
            audit_columns = inspector.get_columns('audit_logs')
            column_names = [col['name'] for col in audit_columns]
            
            required_columns = [
                'id', 'request_id', 'api_key', 'method', 'path', 
                'request_time', 'first_response_time', 'response_time'
            ]
            
            for col in required_columns:
                if col not in column_names:
                    print(f"  ❌ audit_logs表缺少字段: {col}")
                    return False
            
            # 检查是否存在Phase 2.4遗留字段
            legacy_fields = ['model_name', 'routing_time_ms']
            for field in legacy_fields:
                if field in column_names:
                    print(f"  ⚠️  检测到Phase 2.4遗留字段: {field}")
                    return False
            
            print("  ✅ 数据库结构验证通过")
            return True
            
        except Exception as e:
            print(f"  ❌ 数据库结构验证失败: {e}")
            return False
    
    def get_database_stats(self):
        """获取数据库统计信息"""
        try:
            with self.engine.connect() as conn:
                stats = {}
                
                # API Keys统计
                result = conn.execute(text("SELECT COUNT(*) FROM api_keys WHERE is_active = 1"))
                stats['active_api_keys'] = result.scalar()
                
                # 代理路由统计
                result = conn.execute(text("SELECT COUNT(*) FROM proxy_routes WHERE is_active = 1"))
                stats['active_routes'] = result.scalar()
                
                # 审计日志统计
                result = conn.execute(text("SELECT COUNT(*) FROM audit_logs"))
                stats['audit_logs'] = result.scalar()
                
                return stats
        
    except Exception as e:
            print(f"获取数据库统计失败: {e}")
            return None

# 初始化函数（用于脚本直接运行）
def init_database(database_url: str = "sqlite:///./app/data/fastgate.db"):
    """数据库初始化"""
    db_init = DatabaseInitializer(database_url)
    db_init.ensure_database()
    
    # 显示统计信息
    stats = db_init.get_database_stats()
    if stats:
        print("\n📊 数据库统计信息:")
        print(f"  🔑 活跃API Keys: {stats['active_api_keys']}")
        print(f"  🛣️  活跃代理路由: {stats['active_routes']}")
        print(f"  📋 审计日志记录: {stats['audit_logs']}")
    
    print("\n🎉 M-FastGate v0.2.0 数据库准备就绪!")

if __name__ == "__main__":
    # 脚本直接运行时的数据库初始化
    init_database() 