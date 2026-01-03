"""
页面路由 - 服务端渲染页面
"""

from fastapi import APIRouter, Request, Query
from fastapi.responses import HTMLResponse
from pathlib import Path

from trendradar.web.app import templates, get_db, get_config_manager

router = APIRouter(tags=["pages"])


@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """首页 - 热点概览"""
    db = get_db()
    config = get_config_manager()
    
    stats = db.get_stats()
    
    # 获取各平台今日 TOP 10
    platforms = db.get_platforms(platform_type='hotlist')
    platform_news = {}
    for p in platforms:
        news = db.get_news(platform_id=p['id'], limit=10)
        if news:
            platform_news[p['id']] = {
                'name': p['name'],
                'news': news
            }
    
    return templates.TemplateResponse("index.html", {
        "request": request,
        "stats": stats,
        "platform_news": platform_news,
        "page_title": "热点概览"
    })


@router.get("/news", response_class=HTMLResponse)
async def news_list(
    request: Request,
    platform: str = Query(None, description="平台ID"),
    date: str = Query(None, description="日期 YYYY-MM-DD"),
    search: str = Query(None, description="搜索关键词"),
    page: int = Query(1, ge=1, description="页码")
):
    """新闻列表页"""
    db = get_db()
    
    page_size = 50
    offset = (page - 1) * page_size
    
    # 获取新闻列表
    news_list = db.get_news(
        platform_id=platform,
        platform_type='hotlist',
        date=date,
        search=search,
        limit=page_size,
        offset=offset
    )
    
    # 获取总数
    total = db.get_news_count(
        platform_id=platform,
        platform_type='hotlist',
        date=date,
        search=search
    )
    
    # 分页信息
    total_pages = (total + page_size - 1) // page_size
    
    # 获取平台列表和可用日期
    platforms = db.get_platforms(platform_type='hotlist')
    available_dates = db.get_available_dates()
    
    return templates.TemplateResponse("news.html", {
        "request": request,
        "news_list": news_list,
        "platforms": platforms,
        "available_dates": available_dates,
        "current_platform": platform,
        "current_date": date,
        "current_search": search,
        "page": page,
        "total_pages": total_pages,
        "total": total,
        "page_title": "新闻列表"
    })


@router.get("/rss", response_class=HTMLResponse)
async def rss_list(
    request: Request,
    feed: str = Query(None, description="RSS源ID"),
    date: str = Query(None, description="日期 YYYY-MM-DD"),
    search: str = Query(None, description="搜索关键词"),
    page: int = Query(1, ge=1, description="页码")
):
    """RSS 列表页"""
    db = get_db()
    
    page_size = 50
    offset = (page - 1) * page_size
    
    # 获取 RSS 列表
    rss_list = db.get_news(
        platform_id=feed,
        platform_type='rss',
        date=date,
        search=search,
        limit=page_size,
        offset=offset
    )
    
    # 获取总数
    total = db.get_news_count(
        platform_id=feed,
        platform_type='rss',
        date=date,
        search=search
    )
    
    # 分页信息
    total_pages = (total + page_size - 1) // page_size
    
    # 获取 RSS 源列表
    feeds = db.get_platforms(platform_type='rss')
    available_dates = db.get_available_dates()
    
    return templates.TemplateResponse("rss.html", {
        "request": request,
        "rss_list": rss_list,
        "feeds": feeds,
        "available_dates": available_dates,
        "current_feed": feed,
        "current_date": date,
        "current_search": search,
        "page": page,
        "total_pages": total_pages,
        "total": total,
        "page_title": "RSS 订阅"
    })


@router.get("/detail/{news_id}", response_class=HTMLResponse)
async def news_detail(request: Request, news_id: int):
    """新闻详情页"""
    db = get_db()
    
    news = db.get_news_by_id(news_id)
    if not news:
        return templates.TemplateResponse("error.html", {
            "request": request,
            "error": "新闻不存在",
            "code": 404
        }, status_code=404)
    
    rank_history = db.get_rank_history(news_id)
    title_changes = db.get_title_changes(news_id)
    
    return templates.TemplateResponse("detail.html", {
        "request": request,
        "news": news,
        "rank_history": rank_history,
        "title_changes": title_changes,
        "page_title": news['title'][:30] + "..."
    })


@router.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    """配置管理页面"""
    config = get_config_manager()
    
    # 读取关键字配置
    keywords_content = ""
    keywords_path = Path("config/frequency_words.txt")
    if keywords_path.exists():
        keywords_content = keywords_path.read_text(encoding="utf-8")
    
    # 获取报告模式
    report_mode = config.get("report.mode", "current")
    
    return templates.TemplateResponse("settings.html", {
        "request": request,
        "config": config.config,
        "config_raw": config.get_raw(),
        "keywords_content": keywords_content,
        "report_mode": report_mode,
        "page_title": "系统设置"
    })


@router.get("/report", response_class=HTMLResponse)
async def report_page(
    request: Request,
    mode: str = Query(None, description="报告模式"),
    date: str = Query(None, description="日期 YYYY-MM-DD"),
    time: str = Query(None, description="具体时间点")
):
    """报告查看页面"""
    db = get_db()
    config = get_config_manager()
    
    # 获取可用日期
    available_dates = db.get_available_dates()
    
    # 获取当前配置的报告模式（如果未指定）
    if mode is None:
        mode = config.get("report.mode", "current")
    
    return templates.TemplateResponse("report.html", {
        "request": request,
        "available_dates": available_dates,
        "current_mode": mode,
        "current_date": date,
        "current_time": time,
        "page_title": "报告查看"
    })
