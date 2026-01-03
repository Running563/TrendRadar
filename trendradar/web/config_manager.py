"""
配置管理器 - 基于数据库的配置管理

所有配置存储在数据库中，不支持直接修改配置文件
"""

import json
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime

from trendradar.storage.database import Database, DEFAULT_DB_PATH


class ConfigManager:
    """
    配置管理器
    
    基于数据库的配置管理，所有配置存储在 SQLite 数据库中
    支持：
    - 热更新配置
    - 平台管理
    - RSS 源管理
    - 通知渠道管理
    """
    
    _instance: Optional['ConfigManager'] = None
    
    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        self.db_path = db_path
        self._db: Optional[Database] = None
        self._lock = threading.Lock()
        self._config_cache: Dict[str, Any] = {}
        self._cache_time: float = 0
        self._cache_ttl: float = 5.0  # 缓存有效期（秒）
    
    @classmethod
    def get_instance(cls, db_path: str = DEFAULT_DB_PATH) -> 'ConfigManager':
        """获取单例实例"""
        if cls._instance is None or cls._instance.db_path != db_path:
            cls._instance = cls(db_path)
        return cls._instance
    
    @property
    def db(self) -> Database:
        """获取数据库实例"""
        if self._db is None:
            self._db = Database.get_instance(self.db_path)
        return self._db
    
    def _invalidate_cache(self) -> None:
        """使缓存失效"""
        self._cache_time = 0
        self._config_cache.clear()
    
    def _is_cache_valid(self) -> bool:
        """检查缓存是否有效"""
        import time
        return time.time() - self._cache_time < self._cache_ttl
    
    # ========== 基础配置操作 ==========
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        获取配置项，支持点号分隔的键
        
        Args:
            key: 配置键，如 "app.timezone" 或 "report.mode"
            default: 默认值
            
        Returns:
            配置值
        """
        with self._lock:
            result = self.db.execute(
                "SELECT value FROM app_config WHERE key = ?",
                (key,)
            )
            if result:
                try:
                    return json.loads(result[0]['value'])
                except json.JSONDecodeError:
                    return result[0]['value']
            return default
    
    def set(self, key: str, value: Any) -> bool:
        """
        设置配置项
        
        Args:
            key: 配置键
            value: 配置值（会自动 JSON 序列化）
            
        Returns:
            是否设置成功
        """
        with self._lock:
            try:
                json_value = json.dumps(value, ensure_ascii=False)
                self.db.execute("""
                    INSERT INTO app_config (key, value, updated_at)
                    VALUES (?, ?, ?)
                    ON CONFLICT(key) DO UPDATE SET 
                        value = excluded.value,
                        updated_at = excluded.updated_at
                """, (key, json_value, datetime.now().isoformat()))
                self._invalidate_cache()
                return True
            except Exception as e:
                print(f"设置配置失败: {e}")
                return False
    
    def get_all(self) -> Dict[str, Any]:
        """
        获取所有配置，组织成嵌套字典结构
        
        Returns:
            完整配置字典
        """
        with self._lock:
            if self._is_cache_valid() and self._config_cache:
                return self._config_cache.copy()
            
            result = self.db.execute("SELECT key, value FROM app_config")
            config = {}
            
            for row in result:
                key = row['key']
                try:
                    value = json.loads(row['value'])
                except json.JSONDecodeError:
                    value = row['value']
                
                # 将点号分隔的键转换为嵌套字典
                keys = key.split('.')
                current = config
                for k in keys[:-1]:
                    if k not in current:
                        current[k] = {}
                    current = current[k]
                current[keys[-1]] = value
            
            # 添加平台、RSS源和通知渠道
            config['platforms'] = self.get_platforms()
            config['rss'] = config.get('rss', {})
            config['rss']['feeds'] = self.get_rss_feeds()
            config['notification'] = config.get('notification', {})
            config['notification']['channels'] = self.get_notification_channels()
            
            import time
            self._config_cache = config
            self._cache_time = time.time()
            
            return config.copy()
    
    @property
    def config(self) -> Dict[str, Any]:
        """获取完整配置（属性访问）"""
        return self.get_all()
    
    def reload(self) -> bool:
        """重新加载配置（清除缓存）"""
        self._invalidate_cache()
        return True
    
    # ========== 平台管理 ==========
    
    def get_platforms(self) -> List[Dict]:
        """获取热榜平台列表"""
        result = self.db.execute("""
            SELECT id, name, is_active as enabled
            FROM platforms 
            WHERE type = 'hotlist'
            ORDER BY name
        """)
        return [{'id': r['id'], 'name': r['name'], 'enabled': bool(r['enabled'])} for r in result]
    
    def add_platform(self, platform_id: str, name: str, enabled: bool = True) -> bool:
        """添加平台"""
        try:
            self.db.execute("""
                INSERT INTO platforms (id, name, type, is_active, updated_at)
                VALUES (?, ?, 'hotlist', ?, ?)
            """, (platform_id, name, 1 if enabled else 0, datetime.now().isoformat()))
            self._invalidate_cache()
            return True
        except Exception as e:
            print(f"添加平台失败: {e}")
            return False
    
    def update_platform(self, platform_id: str, name: str, enabled: bool = True) -> bool:
        """更新平台"""
        try:
            self.db.execute("""
                UPDATE platforms SET name = ?, is_active = ?, updated_at = ?
                WHERE id = ?
            """, (name, 1 if enabled else 0, datetime.now().isoformat(), platform_id))
            self._invalidate_cache()
            return True
        except Exception as e:
            print(f"更新平台失败: {e}")
            return False
    
    def delete_platform(self, platform_id: str) -> bool:
        """删除平台"""
        try:
            self.db.execute("DELETE FROM platforms WHERE id = ?", (platform_id,))
            self._invalidate_cache()
            return True
        except Exception as e:
            print(f"删除平台失败: {e}")
            return False
    
    def toggle_platform(self, platform_id: str, enabled: bool) -> bool:
        """切换平台启用状态"""
        try:
            self.db.execute("""
                UPDATE platforms SET is_active = ?, updated_at = ?
                WHERE id = ?
            """, (1 if enabled else 0, datetime.now().isoformat(), platform_id))
            self._invalidate_cache()
            return True
        except Exception as e:
            print(f"切换平台状态失败: {e}")
            return False
    
    def set_platforms(self, platforms: List[Dict]) -> bool:
        """批量设置平台"""
        try:
            # 获取现有平台
            existing = {p['id'] for p in self.get_platforms()}
            new_ids = {p['id'] for p in platforms}
            
            # 删除不在新列表中的平台
            for pid in existing - new_ids:
                self.delete_platform(pid)
            
            # 添加或更新平台
            for p in platforms:
                if p['id'] in existing:
                    self.update_platform(p['id'], p['name'], p.get('enabled', True))
                else:
                    self.add_platform(p['id'], p['name'], p.get('enabled', True))
            
            self._invalidate_cache()
            return True
        except Exception as e:
            print(f"批量设置平台失败: {e}")
            return False
    
    # ========== RSS 源管理 ==========
    
    def get_rss_feeds(self) -> List[Dict]:
        """获取 RSS 源列表"""
        result = self.db.execute("""
            SELECT id, name, url, enabled, max_age_days
            FROM rss_feeds
            ORDER BY name
        """)
        feeds = []
        for r in result:
            feed = {
                'id': r['id'],
                'name': r['name'],
                'url': r['url'],
                'enabled': bool(r['enabled'])
            }
            if r['max_age_days'] is not None:
                feed['max_age_days'] = r['max_age_days']
            feeds.append(feed)
        return feeds
    
    def add_rss_feed(self, feed_id: str, name: str, url: str, 
                     enabled: bool = True, max_age_days: Optional[int] = None) -> bool:
        """添加 RSS 源"""
        try:
            self.db.execute("""
                INSERT INTO rss_feeds (id, name, url, enabled, max_age_days, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (feed_id, name, url, 1 if enabled else 0, max_age_days, datetime.now().isoformat()))
            self._invalidate_cache()
            return True
        except Exception as e:
            print(f"添加 RSS 源失败: {e}")
            return False
    
    def update_rss_feed(self, feed_id: str, name: str, url: str,
                        enabled: bool = True, max_age_days: Optional[int] = None) -> bool:
        """更新 RSS 源"""
        try:
            self.db.execute("""
                UPDATE rss_feeds 
                SET name = ?, url = ?, enabled = ?, max_age_days = ?, updated_at = ?
                WHERE id = ?
            """, (name, url, 1 if enabled else 0, max_age_days, datetime.now().isoformat(), feed_id))
            self._invalidate_cache()
            return True
        except Exception as e:
            print(f"更新 RSS 源失败: {e}")
            return False
    
    def delete_rss_feed(self, feed_id: str) -> bool:
        """删除 RSS 源"""
        try:
            self.db.execute("DELETE FROM rss_feeds WHERE id = ?", (feed_id,))
            self._invalidate_cache()
            return True
        except Exception as e:
            print(f"删除 RSS 源失败: {e}")
            return False
    
    def toggle_rss_feed(self, feed_id: str, enabled: bool) -> bool:
        """切换 RSS 源启用状态"""
        try:
            self.db.execute("""
                UPDATE rss_feeds SET enabled = ?, updated_at = ?
                WHERE id = ?
            """, (1 if enabled else 0, datetime.now().isoformat(), feed_id))
            self._invalidate_cache()
            return True
        except Exception as e:
            print(f"切换 RSS 源状态失败: {e}")
            return False
    
    # ========== 通知渠道管理 ==========
    
    def get_notification_channels(self) -> Dict[str, Dict]:
        """获取通知渠道配置"""
        result = self.db.execute("""
            SELECT channel, enabled, config
            FROM notification_channels
        """)
        channels = {}
        for r in result:
            try:
                config = json.loads(r['config'])
            except json.JSONDecodeError:
                config = {}
            channels[r['channel']] = config
        return channels
    
    def get_notification_channel(self, channel: str) -> Optional[Dict]:
        """获取单个通知渠道配置"""
        result = self.db.execute("""
            SELECT enabled, config
            FROM notification_channels
            WHERE channel = ?
        """, (channel,))
        if result:
            try:
                config = json.loads(result[0]['config'])
                config['enabled'] = bool(result[0]['enabled'])
                return config
            except json.JSONDecodeError:
                return {'enabled': bool(result[0]['enabled'])}
        return None
    
    def set_notification_channel(self, channel: str, config: Dict, enabled: bool = False) -> bool:
        """设置通知渠道配置"""
        try:
            json_config = json.dumps(config, ensure_ascii=False)
            self.db.execute("""
                INSERT INTO notification_channels (channel, enabled, config, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(channel) DO UPDATE SET
                    enabled = excluded.enabled,
                    config = excluded.config,
                    updated_at = excluded.updated_at
            """, (channel, 1 if enabled else 0, json_config, datetime.now().isoformat()))
            self._invalidate_cache()
            return True
        except Exception as e:
            print(f"设置通知渠道失败: {e}")
            return False
    
    # ========== 兼容性方法 ==========
    
    def get_raw(self) -> str:
        """
        获取配置的 JSON 格式（兼容旧 API）
        
        Returns:
            JSON 格式的配置字符串
        """
        config = self.get_all()
        return json.dumps(config, ensure_ascii=False, indent=2)
    
    def set_raw(self, content: str) -> bool:
        """
        从 JSON 设置配置（兼容旧 API）
        
        注意：此方法会覆盖所有配置
        
        Args:
            content: JSON 格式的配置字符串
            
        Returns:
            是否设置成功
        """
        try:
            config = json.loads(content)
            if not isinstance(config, dict):
                raise ValueError("配置必须是一个字典")
            
            # 扁平化配置并保存
            def flatten(d: Dict, prefix: str = '') -> Dict[str, Any]:
                items = {}
                for k, v in d.items():
                    key = f"{prefix}.{k}" if prefix else k
                    if isinstance(v, dict) and k not in ['platforms', 'feeds', 'channels']:
                        items.update(flatten(v, key))
                    else:
                        items[key] = v
                return items
            
            flat_config = flatten(config)
            
            with self._lock:
                # 更新基础配置
                for key, value in flat_config.items():
                    if key not in ['platforms', 'rss.feeds', 'notification.channels']:
                        self.set(key, value)
                
                # 更新平台
                if 'platforms' in config:
                    self.set_platforms(config['platforms'])
                
                # 更新 RSS 源
                if 'rss' in config and 'feeds' in config['rss']:
                    for feed in config['rss']['feeds']:
                        if self.db.execute("SELECT id FROM rss_feeds WHERE id = ?", (feed['id'],)):
                            self.update_rss_feed(
                                feed['id'], feed['name'], feed['url'],
                                feed.get('enabled', True), feed.get('max_age_days')
                            )
                        else:
                            self.add_rss_feed(
                                feed['id'], feed['name'], feed['url'],
                                feed.get('enabled', True), feed.get('max_age_days')
                            )
                
                # 更新通知渠道
                if 'notification' in config and 'channels' in config['notification']:
                    for channel, channel_config in config['notification']['channels'].items():
                        self.set_notification_channel(channel, channel_config)
            
            self._invalidate_cache()
            return True
            
        except json.JSONDecodeError as e:
            raise ValueError(f"JSON 格式错误: {e}")
        except Exception as e:
            raise ValueError(f"设置配置失败: {e}")


# 便捷函数
def get_config_manager(db_path: str = DEFAULT_DB_PATH) -> ConfigManager:
    """获取配置管理器实例"""
    return ConfigManager.get_instance(db_path)
