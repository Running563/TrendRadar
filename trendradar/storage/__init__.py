# coding=utf-8
"""
存储模块 - 本地 SQLite 存储

简化版：只支持本地 SQLite + TXT/HTML 文件存储
"""

from trendradar.storage.base import (
    StorageBackend,
    NewsItem,
    NewsData,
    convert_crawl_results_to_news_data,
    convert_news_data_to_results,
)
from trendradar.storage.local import LocalStorageBackend
from trendradar.storage.manager import StorageManager, get_storage_manager

__all__ = [
    # 基础类
    "StorageBackend",
    "NewsItem",
    "NewsData",
    # 转换函数
    "convert_crawl_results_to_news_data",
    "convert_news_data_to_results",
    # 后端实现
    "LocalStorageBackend",
    # 管理器
    "StorageManager",
    "get_storage_manager",
]
