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
        
        from trendradar.crawler.fetcher import DataFetcher
        from trendradar.web.app import get_db, get_config_manager
        
        db = get_db()
        config = get_config_manager()
        
        if crawl_type in ['hotlist', 'all']:
            platforms = config.get_platforms()
            
            # 构建平台 ID 列表
            ids_list = [(p['id'], p['name']) for p in platforms]
            
            # 使用 DataFetcher 抓取数据
            fetcher = DataFetcher()
            results, id_to_name, failed_ids = await asyncio.to_thread(
                fetcher.crawl_websites, ids_list, 500
            )
            
            # 保存到数据库
            crawl_record_id = db.record_crawl(crawl_type='hotlist', total_items=0)
            total_items = 0
            
            for platform_id, titles_data in results.items():
                platform_name = id_to_name.get(platform_id, platform_id)
                
                # 确保平台存在
                db.upsert_platform(
                    platform_id=platform_id,
                    name=platform_name,
                    platform_type='hotlist'
                )
                
                # 保存新闻
                for title, title_info in titles_data.items():
                    ranks = title_info.get('ranks', [])
                    rank = min(ranks) if ranks else 0
                    
                    db.upsert_news(
                        title=title,
                        platform_id=platform_id,
                        url=title_info.get('url', ''),
                        rank=rank,
                        mobile_url=title_info.get('mobileUrl', '')
                    )
                    total_items += 1
                
                db.record_crawl_status(crawl_record_id, platform_id, 'success')
                db.update_platform_status(platform_id, 'success')
            
            # 记录失败的平台（排除已成功记录的）
            recorded_platforms = set(results.keys())
            for failed_id in failed_ids:
                if failed_id not in recorded_platforms:
                    # 确保平台存在
                    db.upsert_platform(
                        platform_id=failed_id,
                        name=id_to_name.get(failed_id, failed_id),
                        platform_type='hotlist'
                    )
                    db.record_crawl_status(crawl_record_id, failed_id, 'failed')
                    db.update_platform_status(failed_id, 'failed')
            
            # 更新抓取记录中的总数
            db.execute(
                "UPDATE crawl_records SET total_items = ? WHERE id = ?",
                (total_items, crawl_record_id)
            )
            
            _crawl_status["message"] = f"热榜抓取完成，共 {total_items} 条"
        
        if crawl_type in ['rss', 'all']:
            rss_config = config.get('rss', {})
            if rss_config.get('enabled'):
                feeds = rss_config.get('feeds', [])
                
                from trendradar.crawler.rss.fetcher import RSSFetcher, RSSFeedConfig
                
                # 构建 RSS 源配置
                feed_configs = [
                    RSSFeedConfig(
                        id=f['id'],
                        name=f.get('name', f['id']),
                        url=f.get('url', ''),
                        enabled=f.get('enabled', True)
                    )
                    for f in feeds if f.get('enabled', True) and f.get('url')
                ]
                
                if feed_configs:
                    crawl_record_id = db.record_crawl(crawl_type='rss', total_items=0)
                    total_items = 0
                    
                    # 使用 RSSFetcher 抓取
                    fetcher = RSSFetcher(feeds=feed_configs)
                    rss_result = await asyncio.to_thread(fetcher.fetch_all)
                    
                    # rss_result 是 RSSData 对象
                    for feed_id, items_list in rss_result.items.items():
                        # 确保 RSS 源存在
                        feed_name = rss_result.id_to_name.get(feed_id, feed_id)
                        feed_config = next((f for f in feed_configs if f.id == feed_id), None)
                        feed_url = feed_config.url if feed_config else ''
                        
                        db.upsert_platform(
                            platform_id=feed_id,
                            name=feed_name,
                            platform_type='rss',
                            feed_url=feed_url
                        )
                        
                        # 保存 RSS 条目（items_list 是 RSSItem 对象列表）
                        for item in items_list:
                            db.upsert_news(
                                title=item.title,
                                platform_id=feed_id,
                                url=item.url,
                                summary=item.summary,
                                author=item.author,
                                published_at=item.published_at
                            )
                            total_items += 1
                        
                        db.record_crawl_status(crawl_record_id, feed_id, 'success')
                        db.update_platform_status(feed_id, 'success')
                    
                    # 记录失败的源
                    for failed_id in rss_result.failed_ids:
                        feed_name = rss_result.id_to_name.get(failed_id, failed_id)
                        db.upsert_platform(
                            platform_id=failed_id,
                            name=feed_name,
                            platform_type='rss'
                        )
                        db.record_crawl_status(crawl_record_id, failed_id, 'failed')
                        db.update_platform_status(failed_id, 'failed')
                    
                    db.execute(
                        "UPDATE crawl_records SET total_items = ? WHERE id = ?",
                        (total_items, crawl_record_id)
                    )
                    
                    _crawl_status["message"] = f"RSS 抓取完成，共 {total_items} 条"
        
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
