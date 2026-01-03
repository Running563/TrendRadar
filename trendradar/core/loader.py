# coding=utf-8
"""
配置加载模块

从数据库加载配置，不再支持直接修改配置文件
"""

import json
from pathlib import Path
from typing import Dict, Any, List, Optional

from trendradar.storage.database import Database, DEFAULT_DB_PATH

from .config import parse_multi_account_config, validate_paired_configs


class ConfigLoader:
    """
    配置加载器
    
    从数据库读取所有配置，爬虫和 Web 共享同一配置源
    """
    
    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        self.db_path = db_path
        self._db: Optional[Database] = None
    
    @property
    def db(self) -> Database:
        """获取数据库实例"""
        if self._db is None:
            self._db = Database.get_instance(self.db_path)
        return self._db
    
    def _get_config(self, key: str, default: Any = None) -> Any:
        """从数据库获取配置项"""
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
    
    def _get_platforms(self) -> List[Dict]:
        """获取热榜平台列表"""
        result = self.db.execute("""
            SELECT id, name, is_active
            FROM platforms 
            WHERE type = 'hotlist' AND is_active = 1
            ORDER BY name
        """)
        return [{'id': r['id'], 'name': r['name']} for r in result]
    
    def _get_rss_feeds(self) -> List[Dict]:
        """获取 RSS 源列表"""
        result = self.db.execute("""
            SELECT id, name, url, enabled, max_age_days
            FROM rss_feeds
            WHERE enabled = 1
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
    
    def _get_notification_channels(self) -> Dict[str, Dict]:
        """获取通知渠道配置"""
        result = self.db.execute("""
            SELECT channel, enabled, config
            FROM notification_channels
        """)
        channels = {}
        for r in result:
            try:
                config = json.loads(r['config'])
                config['enabled'] = bool(r['enabled'])
            except json.JSONDecodeError:
                config = {'enabled': bool(r['enabled'])}
            channels[r['channel']] = config
        return channels
    
    def load(self) -> Dict[str, Any]:
        """
        从数据库加载完整配置
        
        Returns:
            包含所有配置的字典
        """
        print(f"从数据库加载配置: {self.db_path}")
        
        config = {}
        
        # ========== 应用配置 ==========
        config["TIMEZONE"] = self._get_config("app.timezone", "Asia/Shanghai")
        config["SHOW_VERSION_UPDATE"] = self._get_config("app.show_version_update", True)
        config["VERSION_CHECK_URL"] = self._get_config(
            "advanced.version_check_url",
            "https://raw.githubusercontent.com/example/TrendRadar/master/version"
        )
        
        # ========== 爬虫配置 ==========
        config["ENABLE_CRAWLER"] = self._get_config("advanced.crawler.enabled", True)
        config["REQUEST_INTERVAL"] = self._get_config("advanced.crawler.request_interval", 1000)
        config["USE_PROXY"] = self._get_config("advanced.crawler.use_proxy", False)
        config["DEFAULT_PROXY"] = self._get_config("advanced.crawler.default_proxy", "")
        
        # ========== 报告配置 ==========
        config["REPORT_MODE"] = self._get_config("report.mode", "current")
        config["RANK_THRESHOLD"] = self._get_config("report.rank_threshold", 5)
        config["SORT_BY_POSITION_FIRST"] = self._get_config("report.sort_by_position_first", False)
        config["MAX_NEWS_PER_KEYWORD"] = self._get_config("report.max_news_per_keyword", 0)
        config["REVERSE_CONTENT_ORDER"] = self._get_config("report.reverse_content_order", False)
        
        # ========== 通知配置 ==========
        config["ENABLE_NOTIFICATION"] = self._get_config("notification.enabled", False)
        config["MESSAGE_BATCH_SIZE"] = self._get_config("advanced.batch_size.default", 4000)
        config["DINGTALK_BATCH_SIZE"] = self._get_config("advanced.batch_size.dingtalk", 20000)
        config["FEISHU_BATCH_SIZE"] = self._get_config("advanced.batch_size.feishu", 29000)
        config["BARK_BATCH_SIZE"] = self._get_config("advanced.batch_size.bark", 3600)
        config["SLACK_BATCH_SIZE"] = self._get_config("advanced.batch_size.slack", 4000)
        config["BATCH_SEND_INTERVAL"] = self._get_config("advanced.batch_send_interval", 3)
        config["FEISHU_MESSAGE_SEPARATOR"] = self._get_config(
            "advanced.feishu_message_separator", 
            "━━━━━━━━━━━━━━━━━━━"
        )
        config["MAX_ACCOUNTS_PER_CHANNEL"] = self._get_config("advanced.max_accounts_per_channel", 3)
        
        # ========== 推送窗口配置 ==========
        config["PUSH_WINDOW"] = {
            "ENABLED": self._get_config("notification.push_window.enabled", False),
            "TIME_RANGE": {
                "START": self._get_config("notification.push_window.start", "20:00"),
                "END": self._get_config("notification.push_window.end", "22:00"),
            },
            "ONCE_PER_DAY": self._get_config("notification.push_window.once_per_day", True),
        }
        
        # ========== 权重配置 ==========
        config["WEIGHT_CONFIG"] = {
            "RANK_WEIGHT": self._get_config("advanced.weight.rank", 0.6),
            "FREQUENCY_WEIGHT": self._get_config("advanced.weight.frequency", 0.3),
            "HOTNESS_WEIGHT": self._get_config("advanced.weight.hotness", 0.1),
        }
        
        # ========== 平台配置 ==========
        config["PLATFORMS"] = self._get_platforms()
        
        # ========== RSS 配置 ==========
        config["RSS"] = {
            "ENABLED": self._get_config("rss.enabled", True),
            "REQUEST_INTERVAL": self._get_config("advanced.rss.request_interval", 2000),
            "TIMEOUT": self._get_config("advanced.rss.timeout", 15),
            "USE_PROXY": self._get_config("advanced.rss.use_proxy", False),
            "PROXY_URL": self._get_config("advanced.rss.proxy_url", ""),
            "FEEDS": self._get_rss_feeds(),
            "FRESHNESS_FILTER": {
                "ENABLED": self._get_config("rss.freshness_filter.enabled", True),
                "MAX_AGE_DAYS": self._get_config("rss.freshness_filter.max_age_days", 3),
            },
            "NOTIFICATION": {
                "ENABLED": self._get_config("advanced.rss.notification_enabled", True),
            },
        }
        
        # ========== 存储配置 ==========
        config["STORAGE"] = {
            "BACKEND": "local",
            "FORMATS": {
                "SQLITE": self._get_config("storage.formats.sqlite", True),
                "TXT": self._get_config("storage.formats.txt", False),
                "HTML": True,  # HTML 报告始终启用
            },
            "LOCAL": {
                "DATA_DIR": self._get_config("storage.data_dir", "data"),
                "RETENTION_DAYS": self._get_config("storage.retention_days", 0),
            },
            "RETENTION_DAYS": self._get_config("storage.retention_days", 0),
        }
        
        # ========== 通知渠道配置 ==========
        channels = self._get_notification_channels()
        
        # 飞书
        feishu = channels.get("feishu", {})
        config["FEISHU_WEBHOOK_URL"] = feishu.get("webhook_url", "")
        
        # 钉钉
        dingtalk = channels.get("dingtalk", {})
        config["DINGTALK_WEBHOOK_URL"] = dingtalk.get("webhook_url", "")
        
        # 企业微信
        wework = channels.get("wework", {})
        config["WEWORK_WEBHOOK_URL"] = wework.get("webhook_url", "")
        config["WEWORK_MSG_TYPE"] = wework.get("msg_type", "markdown")
        
        # Telegram
        telegram = channels.get("telegram", {})
        config["TELEGRAM_BOT_TOKEN"] = telegram.get("bot_token", "")
        config["TELEGRAM_CHAT_ID"] = telegram.get("chat_id", "")
        
        # 邮件
        email = channels.get("email", {})
        config["EMAIL_FROM"] = email.get("from", "")
        config["EMAIL_PASSWORD"] = email.get("password", "")
        config["EMAIL_TO"] = email.get("to", "")
        config["EMAIL_SMTP_SERVER"] = email.get("smtp_server", "")
        config["EMAIL_SMTP_PORT"] = email.get("smtp_port", "")
        
        # ntfy
        ntfy = channels.get("ntfy", {})
        config["NTFY_SERVER_URL"] = ntfy.get("server_url", "https://ntfy.sh")
        config["NTFY_TOPIC"] = ntfy.get("topic", "")
        config["NTFY_TOKEN"] = ntfy.get("token", "")
        
        # Bark
        bark = channels.get("bark", {})
        config["BARK_URL"] = bark.get("url", "")
        
        # Slack
        slack = channels.get("slack", {})
        config["SLACK_WEBHOOK_URL"] = slack.get("webhook_url", "")
        
        # 打印通知渠道配置来源
        self._print_notification_sources(config)
        
        return config
    
    def _print_notification_sources(self, config: Dict) -> None:
        """打印通知渠道配置来源信息"""
        notification_sources = []
        max_accounts = config["MAX_ACCOUNTS_PER_CHANNEL"]
        
        if config["FEISHU_WEBHOOK_URL"]:
            accounts = parse_multi_account_config(config["FEISHU_WEBHOOK_URL"])
            count = min(len(accounts), max_accounts)
            notification_sources.append(f"飞书({count}个账号)")
        
        if config["DINGTALK_WEBHOOK_URL"]:
            accounts = parse_multi_account_config(config["DINGTALK_WEBHOOK_URL"])
            count = min(len(accounts), max_accounts)
            notification_sources.append(f"钉钉({count}个账号)")
        
        if config["WEWORK_WEBHOOK_URL"]:
            accounts = parse_multi_account_config(config["WEWORK_WEBHOOK_URL"])
            count = min(len(accounts), max_accounts)
            notification_sources.append(f"企业微信({count}个账号)")
        
        if config["TELEGRAM_BOT_TOKEN"] and config["TELEGRAM_CHAT_ID"]:
            tokens = parse_multi_account_config(config["TELEGRAM_BOT_TOKEN"])
            chat_ids = parse_multi_account_config(config["TELEGRAM_CHAT_ID"])
            valid, count = validate_paired_configs(
                {"bot_token": tokens, "chat_id": chat_ids},
                "Telegram",
                required_keys=["bot_token", "chat_id"]
            )
            if valid and count > 0:
                count = min(count, max_accounts)
                notification_sources.append(f"Telegram({count}个账号)")
        
        if config["EMAIL_FROM"] and config["EMAIL_PASSWORD"] and config["EMAIL_TO"]:
            notification_sources.append("邮件")
        
        if config["NTFY_SERVER_URL"] and config["NTFY_TOPIC"]:
            topics = parse_multi_account_config(config["NTFY_TOPIC"])
            tokens = parse_multi_account_config(config["NTFY_TOKEN"])
            if tokens:
                valid, count = validate_paired_configs(
                    {"topic": topics, "token": tokens},
                    "ntfy"
                )
                if valid and count > 0:
                    count = min(count, max_accounts)
                    notification_sources.append(f"ntfy({count}个账号)")
            else:
                count = min(len(topics), max_accounts)
                notification_sources.append(f"ntfy({count}个账号)")
        
        if config["BARK_URL"]:
            accounts = parse_multi_account_config(config["BARK_URL"])
            count = min(len(accounts), max_accounts)
            notification_sources.append(f"Bark({count}个账号)")
        
        if config["SLACK_WEBHOOK_URL"]:
            accounts = parse_multi_account_config(config["SLACK_WEBHOOK_URL"])
            count = min(len(accounts), max_accounts)
            notification_sources.append(f"Slack({count}个账号)")
        
        if notification_sources:
            print(f"通知渠道: {', '.join(notification_sources)}")
            print(f"每个渠道最大账号数: {max_accounts}")
        else:
            print("未配置任何通知渠道")


# 全局加载器实例
_loader: Optional[ConfigLoader] = None


def load_config(db_path: str = DEFAULT_DB_PATH) -> Dict[str, Any]:
    """
    加载配置（从数据库）
    
    Args:
        db_path: 数据库路径
        
    Returns:
        包含所有配置的字典
    """
    global _loader
    if _loader is None or _loader.db_path != db_path:
        _loader = ConfigLoader(db_path)
    return _loader.load()
