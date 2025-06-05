"""
M-FastGate FastAPI 应用入口
"""

from datetime import datetime
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from .config import settings
from .database import create_tables
from .api import admin, proxy, gateway, ui, model_routes
from .services.route_manager import route_manager
from .services.api_gateway_service import api_gateway_service
from . import __version__
from .core.logging_config import setup_logging, get_logger

# Get a logger instance for this module
logger = get_logger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # Initialize logging configuration
    setup_logging()

    # 启动时执行
    logger.info(f"🚀 Starting {settings.app.name} v{settings.app.version}")
    
    # 创建数据库表
    create_tables()
    logger.info("📊 Database tables created")
    
    # 初始化API网关服务
    logger.info("🌐 API Gateway service initialized")
    
    yield
    
    # 关闭时执行
    logger.info("🔄 Shutting down...")
    await route_manager.close()
    await api_gateway_service.close()
    logger.info("✅ Cleanup completed")


# 创建FastAPI应用
app = FastAPI(
    title=settings.app.name,
    version=settings.app.version,
    description="一个基于FastAPI的轻量级网关系统",
    debug=settings.app.debug,
    lifespan=lifespan
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
app.include_router(ui.router, prefix="/admin/ui", tags=["Web管理界面"])  # 新增Web UI路由
app.include_router(gateway.router, tags=["API网关"])  # 新增API网关路由
app.include_router(model_routes.router, prefix="/admin", tags=["模型路由管理"])  # Phase 2.4: 模型路由管理

# 健康检查接口
@app.get("/health")
async def health_check():
    """健康检查接口"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow(),
        "version": settings.app.version,
        "name": settings.app.name,
        "gateway": {
            "backend_url": settings.api_gateway.backend_url,
            "backend_path": settings.api_gateway.backend_path,
            "async_audit": settings.api_gateway.async_audit
        }
    }

# 根路径信息
@app.get("/")
async def root():
    """根路径信息"""
    return {
        "name": settings.app.name,
        "version": settings.app.version,
        "description": "M-FastGate 网关系统",
        "docs_url": "/docs",
        "health_url": "/health",
        "admin_prefix": "/admin",
        "web_ui_url": "/admin/ui",
        "gateway_endpoints": {
            "chat_completions": "/proxy/miniai/v2/chat/completions",
            "smart_routing": "/smart/v1/chat/completions",
            "model_management": "/admin/model-routes"
        }
    }

# 代理路由放在最后，以免覆盖其他路由
app.include_router(proxy.router, tags=["代理转发"])


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host=settings.app.host,
        port=settings.app.port,
        reload=settings.app.debug,
        log_level="info"
    )