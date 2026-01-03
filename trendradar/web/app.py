"""
TrendRadar FastAPI 应用主模块

Web 界面专为移动端优化，配置存储在数据库中
"""

import os
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from trendradar.storage.database import Database

# 获取模块目录
BASE_DIR = Path(__file__).parent

# 数据库实例
db: Database = None

# 配置管理器
config_manager = None


def get_db() -> Database:
    """获取数据库实例"""
    global db
    if db is None:
        db_path = os.environ.get('TRENDRADAR_DB_PATH', 'data/trendradar.db')
        db = Database(db_path)
    return db


def get_config_manager():
    """获取配置管理器(支持热更新)"""
    global config_manager
    if config_manager is None:
        from trendradar.web.config_manager import ConfigManager
        db_path = os.environ.get('TRENDRADAR_DB_PATH', 'data/trendradar.db')
        config_manager = ConfigManager(db_path)
    return config_manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时初始化
    global db, config_manager
    db_path = os.environ.get('TRENDRADAR_DB_PATH', 'data/trendradar.db')
    db = Database(db_path)
    
    from trendradar.web.config_manager import ConfigManager
    config_manager = ConfigManager(db_path)
    
    print(f"[Web] 数据库已连接: {db_path}")
    print(f"[Web] 配置已从数据库加载")
    
    yield
    
    # 关闭时清理
    print("[Web] 服务已停止")


# 创建 FastAPI 应用
app = FastAPI(
    title="TrendRadar",
    description="热点新闻聚合与分析工具 - 移动端优化版",
    version="5.1.0",
    lifespan=lifespan
)

# 挂载静态文件
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

# 模板引擎
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


# 注册路由
from trendradar.web.routes import pages, api, config

app.include_router(pages.router)
app.include_router(api.router, prefix="/api")
app.include_router(config.router, prefix="/config")


@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    """404 错误处理"""
    return templates.TemplateResponse(
        "error.html",
        {"request": request, "error": "页面未找到", "code": 404},
        status_code=404
    )


@app.exception_handler(500)
async def server_error_handler(request: Request, exc):
    """500 错误处理"""
    return templates.TemplateResponse(
        "error.html",
        {"request": request, "error": "服务器内部错误", "code": 500},
        status_code=500
    )
