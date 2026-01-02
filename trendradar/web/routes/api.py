"""
API 路由 - RESTful API
"""

import asyncio
from typing import Optional, List
from fastapi import APIRouter, Query, HTTPException, BackgroundTasks
from pydantic import BaseModel

from trendradar.web.app import get_db, get_config_manager

router = APIRouter(tags=["api"])


# ========== 响应模型 ==========

class NewsItem(BaseModel):
    id: int
    title: str
    platform_id: str
    platform_name: str
    platform_type: str
    rank: int
    url: str
    summary: Optional[str] = ""
    author: Optional[str] = ""
    published_at: Optional[str] = None
    first_crawl_time: str
    last_crawl_time: str


class NewsListResponse(BaseModel):
    items: List[dict]
    total: int
    page: int
    page_size: int
    total_pages: int


class StatsResponse(BaseModel):
    total_news: int
    today_news: int
    last_crawl: Optional[str]
    platform_stats: List[dict]


class CrawlStatusResponse(BaseModel):
    status: str
    message: str


# ========== API 端点 ==========

@router.get("/news", response_model=NewsListResponse)
async def get_news(
    platform: Optional[str] = Query(None, description="平台ID"),
    type: Optional[str] = Query(None, description="类型: hotlist/rss"),
    date: Optional[str] = Query(None, description="日期 YYYY-MM-DD"),
    search: Optional[str] = Query(None, description="搜索关键词"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(50, ge=1, le=100, description="每页数量")
):
    """获取新闻列表"""
    db = get_db()
    
    offset = (page - 1) * page_size
    
    items = db.get_news(
        platform_id=platform,
        platform_type=type,
        date=date,
        search=search,
        limit=page_size,
        offset=offset
    )
    
    total = db.get_news_count(
        platform_id=platform,
        platform_type=type,
        date=date,
        search=search
    )
    
    total_pages = (total + page_size - 1) // page_size
    
    return NewsListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages
    )


@router.get("/news/{news_id}")
async def get_news_detail(news_id: int):
    """获取新闻详情"""
    db = get_db()
    
    news = db.get_news_by_id(news_id)
    if not news:
        raise HTTPException(status_code=404, detail="新闻不存在")
    
    rank_history = db.get_rank_history(news_id)
    title_changes = db.get_title_changes(news_id)
    
    return {
        "news": news,
        "rank_history": rank_history,
        "title_changes": title_changes
    }


@router.get("/platforms")
async def get_platforms(type: Optional[str] = Query(None, description="类型: hotlist/rss")):
    """获取平台列表"""
    db = get_db()
    return db.get_platforms(platform_type=type)


@router.get("/stats", response_model=StatsResponse)
async def get_stats():
    """获取统计信息"""
    db = get_db()
    return db.get_stats()


@router.get("/dates")
async def get_available_dates():
    """获取可用日期列表"""
    db = get_db()
    return db.get_available_dates()


@router.get("/crawl/records")
async def get_crawl_records(limit: int = Query(20, ge=1, le=100)):
    """获取抓取记录"""
    db = get_db()
    return db.get_crawl_records(limit=limit)


# ========== 爬虫控制 ==========

# 爬虫运行状态
_crawl_status = {
    "running": False,
    "last_run": None,
    "message": ""
}


async def run_crawler_task(crawl_type: str):
    """后台运行爬虫任务"""
    global _crawl_status
    
    try:
        _crawl_status["running"] = True
        _crawl_status["message"] = f"正在抓取 {crawl_type} 数据..."
        
        # 导入爬虫模块并运行
        from trendradar.crawler.fetcher import fetch_all_platforms
        from trendradar.web.app import get_db, get_config_manager
        
        db = get_db()
        config = get_config_manager()
        
        if crawl_type in ['hotlist', 'all']:
            platforms = config.get_platforms()
            
            # 抓取热榜数据
            results = await asyncio.to_thread(fetch_all_platforms, platforms)
            
            # 保存到数据库
            crawl_record_id = db.record_crawl(crawl_type='hotlist', total_items=0)
            total_items = 0
            
            for platform_id, news_list in results.items():
                if news_list:
                    # 确保平台存在
                    platform_config = next((p for p in platforms if p['id'] == platform_id), None)
                    if platform_config:
                        db.upsert_platform(
                            platform_id=platform_id,
                            name=platform_config.get('name', platform_id),
                            platform_type='hotlist'
                        )
                    
                    for rank, news in enumerate(news_list, 1):
                        db.upsert_news(
                            title=news.get('title', ''),
                            platform_id=platform_id,
                            url=news.get('url', ''),
                            rank=rank,
                            mobile_url=news.get('mobile_url', '')
                        )
                        total_items += 1
                    
                    db.record_crawl_status(crawl_record_id, platform_id, 'success')
                    db.update_platform_status(platform_id, 'success')
                else:
                    db.record_crawl_status(crawl_record_id, platform_id, 'failed')
                    db.update_platform_status(platform_id, 'failed')
            
            # 更新抓取记录中的总数
            db.execute(
                "UPDATE crawl_records SET total_items = ? WHERE id = ?",
                (total_items, crawl_record_id)
            )
        
        if crawl_type in ['rss', 'all']:
            rss_config = config.get('rss', {})
            if rss_config.get('enabled'):
                feeds = rss_config.get('feeds', [])
                
                from trendradar.crawler.rss.fetcher import fetch_rss_feed
                
                crawl_record_id = db.record_crawl(crawl_type='rss', total_items=0)
                total_items = 0
                
                for feed in feeds:
                    if not feed.get('enabled', True):
                        continue
                    
                    feed_id = feed['id']
                    feed_url = feed.get('url', '')
                    
                    # 确保 RSS 源存在
                    db.upsert_platform(
                        platform_id=feed_id,
                        name=feed.get('name', feed_id),
                        platform_type='rss',
                        feed_url=feed_url
                    )
                    
                    try:
                        items = await asyncio.to_thread(fetch_rss_feed, feed_url)
                        
                        for item in items:
                            db.upsert_news(
                                title=item.get('title', ''),
                                platform_id=feed_id,
                                url=item.get('link', ''),
                                summary=item.get('summary', ''),
                                author=item.get('author', ''),
                                published_at=item.get('published', '')
                            )
                            total_items += 1
                        
                        db.record_crawl_status(crawl_record_id, feed_id, 'success')
                        db.update_platform_status(feed_id, 'success')
                    except Exception as e:
                        db.record_crawl_status(crawl_record_id, feed_id, 'failed', str(e))
                        db.update_platform_status(feed_id, 'failed')
                
                db.execute(
                    "UPDATE crawl_records SET total_items = ? WHERE id = ?",
                    (total_items, crawl_record_id)
                )
        
        from datetime import datetime
        _crawl_status["last_run"] = datetime.now().isoformat()
        _crawl_status["message"] = "抓取完成"
        
    except Exception as e:
        _crawl_status["message"] = f"抓取失败: {str(e)}"
    finally:
        _crawl_status["running"] = False


@router.post("/crawl/trigger")
async def trigger_crawl(
    background_tasks: BackgroundTasks,
    type: str = Query("all", description="抓取类型: hotlist/rss/all")
):
    """手动触发爬虫"""
    global _crawl_status
    
    if _crawl_status["running"]:
        return CrawlStatusResponse(
            status="running",
            message="爬虫正在运行中，请稍后再试"
        )
    
    background_tasks.add_task(run_crawler_task, type)
    
    return CrawlStatusResponse(
        status="started",
        message=f"已启动 {type} 数据抓取任务"
    )


@router.get("/crawl/status")
async def get_crawl_status():
    """获取爬虫运行状态"""
    return _crawl_status
