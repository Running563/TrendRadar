"""
配置管理路由
"""

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel
from typing import Any, Dict, List, Optional

from trendradar.web.app import get_config_manager

router = APIRouter(tags=["config"])


# ========== 请求模型 ==========

class ConfigUpdateRequest(BaseModel):
    key: str
    value: Any


class ConfigRawRequest(BaseModel):
    content: str


class PlatformConfig(BaseModel):
    id: str
    name: str
    enabled: bool = True


class RssFeedConfig(BaseModel):
    id: str
    name: str
    url: str
    enabled: bool = True
    max_age_days: Optional[int] = None


class NotificationChannelConfig(BaseModel):
    channel: str
    config: Dict[str, Any]


# ========== API 端点 ==========

@router.get("/")
async def get_config():
    """获取完整配置"""
    config = get_config_manager()
    return config.config


@router.get("/raw")
async def get_config_raw():
    """获取原始 YAML 配置"""
    config = get_config_manager()
    return {"content": config.get_raw()}


@router.post("/raw")
async def set_config_raw(request: ConfigRawRequest):
    """设置原始 YAML 配置"""
    config = get_config_manager()
    try:
        config.set_raw(request.content)
        return {"success": True, "message": "配置已保存"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/item/{key:path}")
async def get_config_item(key: str):
    """获取单个配置项"""
    config = get_config_manager()
    value = config.get(key)
    if value is None:
        raise HTTPException(status_code=404, detail=f"配置项 {key} 不存在")
    return {"key": key, "value": value}


@router.put("/item")
async def set_config_item(request: ConfigUpdateRequest):
    """设置单个配置项"""
    config = get_config_manager()
    if config.set(request.key, request.value):
        return {"success": True, "message": f"配置项 {request.key} 已更新"}
    raise HTTPException(status_code=500, detail="保存配置失败")


@router.post("/reload")
async def reload_config():
    """重新加载配置"""
    config = get_config_manager()
    config.reload()
    return {"success": True, "message": "配置已重新加载"}


# ========== 平台配置 ==========

@router.get("/platforms")
async def get_platforms_config():
    """获取平台配置列表"""
    config = get_config_manager()
    return config.get_platforms()


@router.put("/platforms")
async def set_platforms_config(platforms: List[PlatformConfig]):
    """更新平台配置列表"""
    config = get_config_manager()
    platforms_data = [p.model_dump() for p in platforms]
    if config.set("platforms", platforms_data):
        return {"success": True, "message": "平台配置已更新"}
    raise HTTPException(status_code=500, detail="保存配置失败")


@router.post("/platforms")
async def add_platform(platform: PlatformConfig):
    """添加平台"""
    config = get_config_manager()
    platforms = config.get_platforms()
    
    # 检查是否已存在
    if any(p['id'] == platform.id for p in platforms):
        raise HTTPException(status_code=400, detail=f"平台 {platform.id} 已存在")
    
    platforms.append(platform.model_dump())
    if config.set("platforms", platforms):
        return {"success": True, "message": f"平台 {platform.id} 已添加"}
    raise HTTPException(status_code=500, detail="保存配置失败")


@router.delete("/platforms/{platform_id}")
async def delete_platform(platform_id: str):
    """删除平台"""
    config = get_config_manager()
    platforms = config.get_platforms()
    
    platforms = [p for p in platforms if p['id'] != platform_id]
    if config.set("platforms", platforms):
        return {"success": True, "message": f"平台 {platform_id} 已删除"}
    raise HTTPException(status_code=500, detail="保存配置失败")


# ========== RSS 配置 ==========

@router.get("/rss")
async def get_rss_config():
    """获取 RSS 配置"""
    config = get_config_manager()
    return config.get("rss", {})


@router.put("/rss")
async def set_rss_config(rss_config: Dict[str, Any]):
    """更新 RSS 配置"""
    config = get_config_manager()
    if config.set("rss", rss_config):
        return {"success": True, "message": "RSS 配置已更新"}
    raise HTTPException(status_code=500, detail="保存配置失败")


@router.get("/rss/feeds")
async def get_rss_feeds():
    """获取 RSS 源列表"""
    config = get_config_manager()
    return config.get_rss_feeds()


@router.post("/rss/feeds")
async def add_rss_feed(feed: RssFeedConfig):
    """添加 RSS 源"""
    config = get_config_manager()
    feeds = config.get_rss_feeds()
    
    # 检查是否已存在
    if any(f['id'] == feed.id for f in feeds):
        raise HTTPException(status_code=400, detail=f"RSS 源 {feed.id} 已存在")
    
    feed_data = feed.model_dump()
    if feed_data.get('max_age_days') is None:
        del feed_data['max_age_days']
    
    feeds.append(feed_data)
    if config.set("rss.feeds", feeds):
        return {"success": True, "message": f"RSS 源 {feed.id} 已添加"}
    raise HTTPException(status_code=500, detail="保存配置失败")


@router.delete("/rss/feeds/{feed_id}")
async def delete_rss_feed(feed_id: str):
    """删除 RSS 源"""
    config = get_config_manager()
    feeds = config.get_rss_feeds()
    
    feeds = [f for f in feeds if f['id'] != feed_id]
    if config.set("rss.feeds", feeds):
        return {"success": True, "message": f"RSS 源 {feed_id} 已删除"}
    raise HTTPException(status_code=500, detail="保存配置失败")


# ========== 通知配置 ==========

@router.get("/notification")
async def get_notification_config():
    """获取通知配置"""
    config = get_config_manager()
    return config.get("notification", {})


@router.put("/notification")
async def set_notification_config(notification_config: Dict[str, Any]):
    """更新通知配置"""
    config = get_config_manager()
    if config.set("notification", notification_config):
        return {"success": True, "message": "通知配置已更新"}
    raise HTTPException(status_code=500, detail="保存配置失败")


@router.put("/notification/channel")
async def set_notification_channel(channel_config: NotificationChannelConfig):
    """更新单个通知渠道配置"""
    config = get_config_manager()
    key = f"notification.channels.{channel_config.channel}"
    if config.set(key, channel_config.config):
        return {"success": True, "message": f"通知渠道 {channel_config.channel} 已更新"}
    raise HTTPException(status_code=500, detail="保存配置失败")


# ========== 表单提交处理 ==========

@router.post("/save")
async def save_config_form(request: Request):
    """处理表单提交的配置保存"""
    config = get_config_manager()
    
    form_data = await request.form()
    
    # 转换表单数据
    content = form_data.get("config_content", "")
    
    if content:
        try:
            config.set_raw(content)
            return RedirectResponse(url="/settings?saved=1", status_code=303)
        except ValueError as e:
            return RedirectResponse(url=f"/settings?error={str(e)}", status_code=303)
    
    return RedirectResponse(url="/settings", status_code=303)
