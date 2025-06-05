"""
Web管理界面路由
"""

from fastapi import APIRouter, Request, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
import os

from ..database import get_db
from ..middleware.auth import verify_admin_token
from ..config import settings

router = APIRouter()

# 设置模板目录
templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_class=HTMLResponse)
async def admin_dashboard(
    request: Request,
    token: str = Depends(verify_admin_token)
):
    """
    管理面板首页
    """
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "title": "M-FastGate 管理面板",
        "gateway_url": f"http://{request.client.host}:8514",
        "api_base": "/admin"
    })


@router.get("/keys", response_class=HTMLResponse)
async def api_keys_page(
    request: Request,
    token: str = Depends(verify_admin_token)
):
    """
    API Key 管理页面
    """
    return templates.TemplateResponse("api_keys.html", {
        "request": request,
        "title": "API Key 管理",
        "api_base": "/admin"
    })


@router.get("/logs", response_class=HTMLResponse)
async def audit_logs_page(
    request: Request,
    token: str = Depends(verify_admin_token)
):
    """
    审计日志页面
    """
    return templates.TemplateResponse("audit_logs.html", {
        "request": request,
        "title": "审计日志",
        "api_base": "/admin"
    })


# 静态文件服务
@router.get("/static/{file_path:path}")
async def serve_static(file_path: str):
    """
    服务静态文件
    """
    static_file = f"app/static/{file_path}"
    if os.path.exists(static_file):
        return FileResponse(static_file)
    else:
        raise HTTPException(status_code=404, detail="File not found") 