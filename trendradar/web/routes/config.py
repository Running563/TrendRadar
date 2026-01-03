"""
配置管理路由

所有配置存储在数据库中，不支持直接修改配置文件
"""

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel
from typing import Any, Dict, List, Optional

from trendradar.web.config_manager import get_config_manager

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
    enabled: bool = False


# ========== API 端点 ==========

@router.get("/")
async def get_config():
    """获取完整配置"""
    config = get_config_manager()
    return config.config


@router.get("/raw")
async def get_config_raw():
    """获取 JSON 格式配置"""
    config = get_config_manager()
    return {"content": config.get_raw()}


@router.post("/raw")
async def set_config_raw(request: ConfigRawRequest):
    """设置 JSON 格式配置"""
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
    """重新加载配置（清除缓存）"""
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
    if config.set_platforms(platforms_data):
        return {"success": True, "message": "平台配置已更新"}
    raise HTTPException(status_code=500, detail="保存配置失败")


@router.post("/platforms")
async def add_platform(platform: PlatformConfig):
    """添加平台"""
    config = get_config_manager()
    
    # 检查是否已存在
    platforms = config.get_platforms()
    if any(p['id'] == platform.id for p in platforms):
        raise HTTPException(status_code=400, detail=f"平台 {platform.id} 已存在")
    
    if config.add_platform(platform.id, platform.name, platform.enabled):
        return {"success": True, "message": f"平台 {platform.id} 已添加"}
    raise HTTPException(status_code=500, detail="保存配置失败")


@router.put("/platforms/{platform_id}")
async def update_platform(platform_id: str, platform: PlatformConfig):
    """更新平台"""
    config = get_config_manager()
    if config.update_platform(platform_id, platform.name, platform.enabled):
        return {"success": True, "message": f"平台 {platform_id} 已更新"}
    raise HTTPException(status_code=500, detail="保存配置失败")


@router.delete("/platforms/{platform_id}")
async def delete_platform(platform_id: str):
    """删除平台"""
    config = get_config_manager()
    if config.delete_platform(platform_id):
        return {"success": True, "message": f"平台 {platform_id} 已删除"}
    raise HTTPException(status_code=500, detail="保存配置失败")


@router.put("/platforms/{platform_id}/toggle")
async def toggle_platform(platform_id: str, request: Dict[str, Any]):
    """切换平台启用状态"""
    config = get_config_manager()
    enabled = request.get("enabled", True)
    if config.toggle_platform(platform_id, enabled):
        return {"success": True, "message": f"平台 {platform_id} 已{'启用' if enabled else '禁用'}"}
    raise HTTPException(status_code=500, detail="操作失败")


# ========== RSS 配置 ==========

@router.get("/rss")
async def get_rss_config():
    """获取 RSS 配置"""
    config = get_config_manager()
    return {
        "enabled": config.get("rss.enabled", True),
        "freshness_filter": {
            "enabled": config.get("rss.freshness_filter.enabled", True),
            "max_age_days": config.get("rss.freshness_filter.max_age_days", 3)
        },
        "feeds": config.get_rss_feeds()
    }


@router.put("/rss")
async def set_rss_config(rss_config: Dict[str, Any]):
    """更新 RSS 配置"""
    config = get_config_manager()
    
    # 更新基础配置
    if "enabled" in rss_config:
        config.set("rss.enabled", rss_config["enabled"])
    
    if "freshness_filter" in rss_config:
        ff = rss_config["freshness_filter"]
        if "enabled" in ff:
            config.set("rss.freshness_filter.enabled", ff["enabled"])
        if "max_age_days" in ff:
            config.set("rss.freshness_filter.max_age_days", ff["max_age_days"])
    
    return {"success": True, "message": "RSS 配置已更新"}


@router.get("/rss/feeds")
async def get_rss_feeds():
    """获取 RSS 源列表"""
    config = get_config_manager()
    return config.get_rss_feeds()


@router.post("/rss/feeds")
async def add_rss_feed(feed: RssFeedConfig):
    """添加 RSS 源"""
    config = get_config_manager()
    
    # 检查是否已存在
    feeds = config.get_rss_feeds()
    if any(f['id'] == feed.id for f in feeds):
        raise HTTPException(status_code=400, detail=f"RSS 源 {feed.id} 已存在")
    
    if config.add_rss_feed(feed.id, feed.name, feed.url, feed.enabled, feed.max_age_days):
        return {"success": True, "message": f"RSS 源 {feed.id} 已添加"}
    raise HTTPException(status_code=500, detail="保存配置失败")


@router.put("/rss/feeds/{feed_id}")
async def update_rss_feed(feed_id: str, feed: RssFeedConfig):
    """更新 RSS 源"""
    config = get_config_manager()
    if config.update_rss_feed(feed_id, feed.name, feed.url, feed.enabled, feed.max_age_days):
        return {"success": True, "message": f"RSS 源 {feed_id} 已更新"}
    raise HTTPException(status_code=500, detail="保存配置失败")


@router.delete("/rss/feeds/{feed_id}")
async def delete_rss_feed(feed_id: str):
    """删除 RSS 源"""
    config = get_config_manager()
    if config.delete_rss_feed(feed_id):
        return {"success": True, "message": f"RSS 源 {feed_id} 已删除"}
    raise HTTPException(status_code=500, detail="保存配置失败")


@router.put("/rss/feeds/{feed_id}/toggle")
async def toggle_rss_feed(feed_id: str, request: Dict[str, Any]):
    """切换 RSS 源启用状态"""
    config = get_config_manager()
    enabled = request.get("enabled", True)
    if config.toggle_rss_feed(feed_id, enabled):
        return {"success": True, "message": f"RSS 源 {feed_id} 已{'启用' if enabled else '禁用'}"}
    raise HTTPException(status_code=500, detail="操作失败")


# ========== 通知配置 ==========

@router.get("/notification")
async def get_notification_config():
    """获取通知配置"""
    config = get_config_manager()
    return {
        "enabled": config.get("notification.enabled", False),
        "push_window": {
            "enabled": config.get("notification.push_window.enabled", False),
            "start": config.get("notification.push_window.start", "20:00"),
            "end": config.get("notification.push_window.end", "22:00"),
            "once_per_day": config.get("notification.push_window.once_per_day", True)
        },
        "channels": config.get_notification_channels()
    }


@router.put("/notification")
async def set_notification_config(notification_config: Dict[str, Any]):
    """更新通知配置"""
    config = get_config_manager()
    
    if "enabled" in notification_config:
        config.set("notification.enabled", notification_config["enabled"])
    
    if "push_window" in notification_config:
        pw = notification_config["push_window"]
        if "enabled" in pw:
            config.set("notification.push_window.enabled", pw["enabled"])
        if "start" in pw:
            config.set("notification.push_window.start", pw["start"])
        if "end" in pw:
            config.set("notification.push_window.end", pw["end"])
        if "once_per_day" in pw:
            config.set("notification.push_window.once_per_day", pw["once_per_day"])
    
    return {"success": True, "message": "通知配置已更新"}


@router.get("/notification/channel/{channel}")
async def get_notification_channel(channel: str):
    """获取单个通知渠道配置"""
    config = get_config_manager()
    channel_config = config.get_notification_channel(channel)
    if channel_config is None:
        raise HTTPException(status_code=404, detail=f"通知渠道 {channel} 不存在")
    return {"channel": channel, "config": channel_config}


@router.put("/notification/channel")
async def set_notification_channel(channel_config: NotificationChannelConfig):
    """更新单个通知渠道配置"""
    config = get_config_manager()
    if config.set_notification_channel(
        channel_config.channel, 
        channel_config.config, 
        channel_config.enabled
    ):
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
