# coding=utf-8
"""
TrendRadar - 热点新闻聚合与分析工具 (Web版)

使用方式:
  python -m trendradar        # 模块执行（命令行爬取）
  trendradar                  # 安装后执行（命令行爬取）
  trendradar-web              # 启动 Web 服务
"""

from trendradar.context import AppContext

__version__ = "5.0.0"
__all__ = ["AppContext", "__version__"]
