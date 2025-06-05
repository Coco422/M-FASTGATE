"""
数据库连接和配置
"""

import os
from sqlalchemy import create_engine, MetaData
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from .config import settings

# 创建数据库引擎
engine = create_engine(
    settings.database['url'],
    echo=settings.database['echo'],
    connect_args={"check_same_thread": False} if "sqlite" in settings.database['url'] else {}
)

# 创建会话工厂
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 创建基础模型类
Base = declarative_base()

# 元数据
metadata = MetaData()


def get_db():
    """
    获取数据库会话
    
    Yields:
        数据库会话
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables():
    """
    创建所有表
    """
    # 确保日志目录存在
    log_dir = os.path.dirname(settings.logging['file'])
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    # 导入所有模型以确保它们被注册
    from .models import api_key, audit_log, proxy_route
    
    # 创建所有表
    Base.metadata.create_all(bind=engine)


def drop_tables():
    """
    删除所有表（仅用于测试）
    """
    Base.metadata.drop_all(bind=engine) 