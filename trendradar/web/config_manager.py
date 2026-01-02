"""
配置管理器 - 支持热更新
"""

import os
import yaml
from pathlib import Path
from typing import Any, Dict, Optional
from datetime import datetime
import threading


class ConfigManager:
    """配置管理器，支持热更新"""
    
    def __init__(self, config_path: str = "config/config.yaml"):
        self.config_path = Path(config_path)
        self._config: Dict[str, Any] = {}
        self._last_modified: float = 0
        self._lock = threading.Lock()
        self._load_config()
    
    def _load_config(self) -> None:
        """加载配置文件"""
        if not self.config_path.exists():
            self._config = self._get_default_config()
            self._save_config()
            return
        
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self._config = yaml.safe_load(f) or {}
            self._last_modified = self.config_path.stat().st_mtime
        except Exception as e:
            print(f"加载配置文件失败: {e}")
            self._config = self._get_default_config()
    
    def _save_config(self) -> bool:
        """保存配置文件"""
        try:
            # 确保目录存在
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(self.config_path, 'w', encoding='utf-8') as f:
                yaml.dump(self._config, f, allow_unicode=True, 
                         default_flow_style=False, sort_keys=False)
            self._last_modified = self.config_path.stat().st_mtime
            return True
        except Exception as e:
            print(f"保存配置文件失败: {e}")
            return False
    
    def _get_default_config(self) -> Dict[str, Any]:
        """获取默认配置"""
        return {
            "app": {
                "timezone": "Asia/Shanghai",
                "show_version_update": True
            },
            "platforms": [
                {"id": "toutiao", "name": "今日头条"},
                {"id": "baidu", "name": "百度热搜"},
                {"id": "weibo", "name": "微博热搜"},
                {"id": "zhihu", "name": "知乎热榜"},
                {"id": "douyin", "name": "抖音热榜"},
                {"id": "bilibili", "name": "B站热搜"},
                {"id": "wallstreet", "name": "华尔街见闻"},
                {"id": "thepaper", "name": "澎湃新闻"},
                {"id": "cls", "name": "财联社"},
                {"id": "ifeng", "name": "凤凰网"},
                {"id": "tieba", "name": "贴吧"}
            ],
            "rss": {
                "enabled": True,
                "freshness_filter": {
                    "enabled": True,
                    "max_age_days": 7
                },
                "feeds": []
            },
            "report": {
                "mode": "daily",
                "rank_threshold": 10,
                "sort_by_position_first": True,
                "max_news_per_keyword": 10,
                "reverse_content_order": False
            },
            "notification": {
                "enabled": False,
                "push_window": {
                    "enabled": False,
                    "start": "08:00",
                    "end": "22:00",
                    "once_per_day": True
                },
                "channels": {
                    "feishu": {"webhook_url": ""},
                    "dingtalk": {"webhook_url": ""},
                    "wework": {"webhook_url": "", "msg_type": "markdown"},
                    "telegram": {"bot_token": "", "chat_id": ""},
                    "ntfy": {"server_url": "", "topic": "", "token": ""},
                    "bark": {"url": ""},
                    "slack": {"webhook_url": ""}
                }
            },
            "storage": {
                "backend": "local",
                "formats": {
                    "sqlite": True,
                    "txt": False
                },
                "local": {
                    "data_dir": "data",
                    "retention_days": 30
                }
            }
        }
    
    def reload(self) -> bool:
        """重新加载配置"""
        with self._lock:
            self._load_config()
            return True
    
    def check_and_reload(self) -> bool:
        """检查配置文件是否更新，如果更新则重新加载"""
        if not self.config_path.exists():
            return False
        
        current_mtime = self.config_path.stat().st_mtime
        if current_mtime > self._last_modified:
            return self.reload()
        return False
    
    @property
    def config(self) -> Dict[str, Any]:
        """获取配置(自动检查更新)"""
        self.check_and_reload()
        return self._config
    
    def get(self, key: str, default: Any = None) -> Any:
        """获取配置项，支持点号分隔的键"""
        self.check_and_reload()
        
        keys = key.split('.')
        value = self._config
        
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default
            
            if value is None:
                return default
        
        return value
    
    def set(self, key: str, value: Any) -> bool:
        """设置配置项，支持点号分隔的键"""
        with self._lock:
            keys = key.split('.')
            config = self._config
            
            # 遍历到倒数第二层
            for k in keys[:-1]:
                if k not in config:
                    config[k] = {}
                config = config[k]
            
            # 设置最后一层的值
            config[keys[-1]] = value
            
            return self._save_config()
    
    def update(self, updates: Dict[str, Any]) -> bool:
        """批量更新配置"""
        with self._lock:
            self._deep_merge(self._config, updates)
            return self._save_config()
    
    def _deep_merge(self, base: Dict, updates: Dict) -> None:
        """深度合并字典"""
        for key, value in updates.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._deep_merge(base[key], value)
            else:
                base[key] = value
    
    def get_raw(self) -> str:
        """获取原始 YAML 内容"""
        if self.config_path.exists():
            with open(self.config_path, 'r', encoding='utf-8') as f:
                return f.read()
        return ""
    
    def set_raw(self, content: str) -> bool:
        """设置原始 YAML 内容"""
        try:
            # 先验证 YAML 格式
            parsed = yaml.safe_load(content)
            if not isinstance(parsed, dict):
                raise ValueError("配置必须是一个字典")
            
            with self._lock:
                self._config = parsed
                return self._save_config()
        except yaml.YAMLError as e:
            raise ValueError(f"YAML 格式错误: {e}")
    
    def get_platforms(self) -> list:
        """获取平台列表"""
        return self.get('platforms', [])
    
    def get_rss_feeds(self) -> list:
        """获取 RSS 源列表"""
        return self.get('rss.feeds', [])
    
    def get_notification_channels(self) -> Dict:
        """获取通知渠道配置"""
        return self.get('notification.channels', {})
