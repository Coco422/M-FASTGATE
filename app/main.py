"""
M-FastGate v0.3.0 FastAPI 应用入口
"""

from datetime import datetime
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from .config import settings
from .database import create_tables
from .api import admin, proxy, ui
from .core.logging_config import setup_logging, get_logger

# Get a logger instance for this module
logger = get_logger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # Initialize logging configuration
    setup_logging()

    # 启动时执行
    logger.info(f"🚀 Starting {settings.app['name']} v{settings.app['version']}")
    
    # 创建数据库表
    create_tables()
    logger.info("📊 Database tables created")
    
    # 初始化代理引擎服务
    logger.info("🌐 Proxy engine initialized")
    
    yield
    
    # 关闭时执行
    logger.info("🔄 Shutting down...")
    logger.info("✅ Cleanup completed")


# 创建FastAPI应用
app = FastAPI(
    title=settings.app["name"],
    version=settings.app["version"],
    description="一个基于FastAPI的轻量级网关系统",
    debug=settings.app["debug"],
    lifespan=lifespan,
    root_path="/ai-fg"
)

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应该限制具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(admin.router, prefix="/admin", tags=["管理接口"])
app.include_router(ui.router, prefix="/admin/ui", tags=["Web管理界面"])

# 健康检查接口
@app.get("/health")
async def health_check():
    """健康检查接口"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow(),
        "version": settings.app["version"],
        "name": settings.app["name"],
        "proxy": {
            "timeout": settings.proxy["timeout"],
            "max_retries": settings.proxy["max_retries"],
            "enable_streaming": settings.proxy["enable_streaming"],
            "async_audit": settings.proxy["async_audit"]
        }
    }

# 根路径信息
@app.get("/")
async def root():
    """根路径信息"""
    return {
        "name": settings.app["name"],
        "version": settings.app["version"],
        "description": "M-FastGate v0.3.0 通用代理网关",
        "docs_url": "/docs",
        "health_url": "/health",
        "admin_prefix": "/admin",
        "web_ui_url": "/admin/ui",
        "proxy_endpoints": {
            "universal_proxy": "/{path:path}",
            "route_management": "/admin/routes",
            "audit_logs": "/admin/logs",
            "metrics": "/admin/metrics"
        }
    }

# 代理路由放在最后，以免覆盖其他路由
app.include_router(proxy.router, tags=["代理转发"])


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host=settings.app["host"],
        port=settings.app["port"],
        reload=settings.app["debug"],
        log_level="info"
    )