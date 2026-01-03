# coding=utf-8
"""
存储管理器 - 统一管理本地数据库存储

简化版：只支持本地 SQLite 数据库存储
"""

from typing import Optional

from trendradar.storage.base import StorageBackend, NewsData, RSSData


# 存储管理器单例
_storage_manager: Optional["StorageManager"] = None


class StorageManager:
    """
    存储管理器

    功能：
    - 管理本地 SQLite 数据库存储
    - 提供统一的存储接口
    """

    def __init__(
        self,
        data_dir: str = "data",
        enable_txt: bool = False,
        enable_html: bool = True,
        retention_days: int = 0,
        timezone: str = "Asia/Shanghai",
    ):
        """
        初始化存储管理器

        Args:
            data_dir: 本地数据目录
            enable_txt: 是否启用 TXT 快照
            enable_html: 是否启用 HTML 报告
            retention_days: 数据保留天数（0 = 无限制）
            timezone: 时区配置（默认 Asia/Shanghai）
        """
        self.data_dir = data_dir
        self.enable_txt = enable_txt
        self.enable_html = enable_html
        self.retention_days = retention_days
        self.timezone = timezone

        self._backend: Optional[StorageBackend] = None

    def get_backend(self) -> StorageBackend:
        """获取存储后端实例"""
        if self._backend is None:
            from trendradar.storage.local import LocalStorageBackend

            self._backend = LocalStorageBackend(
                data_dir=self.data_dir,
                enable_txt=self.enable_txt,
                enable_html=self.enable_html,
                timezone=self.timezone,
            )
            print(f"[存储管理器] 使用本地存储后端 (数据目录: {self.data_dir})")

        return self._backend

    def save_news_data(self, data: NewsData) -> bool:
        """保存新闻数据"""
        return self.get_backend().save_news_data(data)

    def save_rss_data(self, data: RSSData) -> bool:
        """保存 RSS 数据"""
        return self.get_backend().save_rss_data(data)

    def get_rss_data(self, date: Optional[str] = None) -> Optional[RSSData]:
        """获取指定日期的所有 RSS 数据（当日汇总模式）"""
        return self.get_backend().get_rss_data(date)

    def get_latest_rss_data(self, date: Optional[str] = None) -> Optional[RSSData]:
        """获取最新一次抓取的 RSS 数据（当前榜单模式）"""
        return self.get_backend().get_latest_rss_data(date)

    def detect_new_rss_items(self, current_data: RSSData) -> dict:
        """检测新增的 RSS 条目（增量模式）"""
        return self.get_backend().detect_new_rss_items(current_data)

    def get_today_all_data(self, date: Optional[str] = None) -> Optional[NewsData]:
        """获取当天所有数据"""
        return self.get_backend().get_today_all_data(date)

    def get_latest_crawl_data(self, date: Optional[str] = None) -> Optional[NewsData]:
        """获取最新抓取数据"""
        return self.get_backend().get_latest_crawl_data(date)

    def detect_new_titles(self, current_data: NewsData) -> dict:
        """检测新增标题"""
        return self.get_backend().detect_new_titles(current_data)

    def save_txt_snapshot(self, data: NewsData) -> Optional[str]:
        """保存 TXT 快照"""
        return self.get_backend().save_txt_snapshot(data)

    def save_html_report(self, html_content: str, filename: str, is_summary: bool = False) -> Optional[str]:
        """保存 HTML 报告"""
        return self.get_backend().save_html_report(html_content, filename, is_summary)

    def is_first_crawl_today(self, date: Optional[str] = None) -> bool:
        """检查是否是当天第一次抓取"""
        return self.get_backend().is_first_crawl_today(date)

    def cleanup(self) -> None:
        """清理资源"""
        if self._backend:
            self._backend.cleanup()

    def cleanup_old_data(self) -> int:
        """
        清理过期数据

        Returns:
            删除的日期目录数量
        """
        if self.retention_days > 0:
            return self.get_backend().cleanup_old_data(self.retention_days)
        return 0

    @property
    def backend_name(self) -> str:
        """获取当前后端名称"""
        return self.get_backend().backend_name

    @property
    def supports_txt(self) -> bool:
        """是否支持 TXT 快照"""
        return self.get_backend().supports_txt

    # === 推送记录相关方法 ===

    def has_pushed_today(self, date: Optional[str] = None) -> bool:
        """
        检查指定日期是否已推送过

        Args:
            date: 日期字符串（YYYY-MM-DD），默认为今天

        Returns:
            是否已推送
        """
        return self.get_backend().has_pushed_today(date)

    def record_push(self, report_type: str, date: Optional[str] = None) -> bool:
        """
        记录推送

        Args:
            report_type: 报告类型
            date: 日期字符串（YYYY-MM-DD），默认为今天

        Returns:
            是否记录成功
        """
        return self.get_backend().record_push(report_type, date)


def get_storage_manager(
    data_dir: str = "data",
    enable_txt: bool = False,
    enable_html: bool = True,
    retention_days: int = 0,
    timezone: str = "Asia/Shanghai",
    force_new: bool = False,
) -> StorageManager:
    """
    获取存储管理器单例

    Args:
        data_dir: 本地数据目录
        enable_txt: 是否启用 TXT 快照
        enable_html: 是否启用 HTML 报告
        retention_days: 数据保留天数（0 = 无限制）
        timezone: 时区配置（默认 Asia/Shanghai）
        force_new: 是否强制创建新实例

    Returns:
        StorageManager 实例
    """
    global _storage_manager

    if _storage_manager is None or force_new:
        _storage_manager = StorageManager(
            data_dir=data_dir,
            enable_txt=enable_txt,
            enable_html=enable_html,
            retention_days=retention_days,
            timezone=timezone,
        )

    return _storage_manager
