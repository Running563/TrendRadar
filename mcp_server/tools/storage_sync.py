# coding=utf-8
"""
存储工具（简化版）

简化版：仅支持本地 SQLite 存储，配置从数据库读取
"""

import re
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
import json

from ..utils.errors import MCPError


class StorageSyncTools:
    """存储工具类（简化版：仅本地存储）"""

    def __init__(self, project_root: str = None):
        """
        初始化存储工具

        Args:
            project_root: 项目根目录
        """
        if project_root:
            self.project_root = Path(project_root)
        else:
            current_file = Path(__file__)
            self.project_root = current_file.parent.parent.parent

        self._db = None

    @property
    def db(self):
        """获取数据库实例"""
        if self._db is None:
            from trendradar.storage.database import Database, DEFAULT_DB_PATH
            self._db = Database.get_instance(DEFAULT_DB_PATH)
        return self._db

    def _get_config(self, key: str, default=None):
        """从数据库获取配置"""
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

    def _get_local_data_dir(self) -> Path:
        """获取本地数据目录"""
        data_dir = self._get_config("storage.data_dir", "data")
        return self.project_root / data_dir

    def _get_local_dates(self) -> List[str]:
        """获取本地可用的日期列表"""
        local_dir = self._get_local_data_dir()
        dates = []

        # 检查 news 目录中的 .db 文件
        news_dir = local_dir / "news"
        if news_dir.exists():
            for db_file in news_dir.glob("*.db"):
                # 文件名格式：YYYY-MM-DD.db
                date_str = db_file.stem
                if re.match(r'\d{4}-\d{2}-\d{2}', date_str):
                    dates.append(date_str)

        return sorted(set(dates), reverse=True)

    def _calculate_dir_size(self, path: Path) -> int:
        """计算目录大小（字节）"""
        total_size = 0
        if path.exists():
            for item in path.rglob("*"):
                if item.is_file():
                    total_size += item.stat().st_size
        return total_size

    def sync_from_remote(self, days: int = 7) -> Dict:
        """
        从远程存储拉取数据到本地（已禁用）

        Args:
            days: 拉取最近 N 天的数据

        Returns:
            提示远程存储已禁用的信息
        """
        return {
            "success": False,
            "error": {
                "code": "REMOTE_DISABLED",
                "message": "远程存储功能已禁用",
                "suggestion": "此版本仅支持本地 SQLite 存储，无需从远程同步数据"
            }
        }

    def get_storage_status(self) -> Dict:
        """
        获取存储配置和状态

        Returns:
            存储状态字典
        """
        try:
            # 本地存储状态
            data_dir = self._get_config("storage.data_dir", "data")
            retention_days = self._get_config("storage.retention_days", 0)
            local_dir = self._get_local_data_dir()
            local_size = self._calculate_dir_size(local_dir)
            local_dates = self._get_local_dates()

            local_status = {
                "data_dir": data_dir,
                "retention_days": retention_days,
                "total_size": f"{local_size / 1024 / 1024:.2f} MB",
                "total_size_bytes": local_size,
                "date_count": len(local_dates),
                "earliest_date": local_dates[-1] if local_dates else None,
                "latest_date": local_dates[0] if local_dates else None,
            }

            return {
                "success": True,
                "backend": "local",
                "local": local_status,
                "remote": {
                    "configured": False,
                    "message": "远程存储功能已禁用"
                },
            }

        except MCPError as e:
            return {
                "success": False,
                "error": e.to_dict()
            }
        except Exception as e:
            return {
                "success": False,
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": str(e)
                }
            }

    def list_available_dates(self, source: str = "both") -> Dict:
        """
        列出可用的日期范围

        Args:
            source: 数据来源
                - "local": 仅本地
                - "remote": 仅远程（已禁用）
                - "both": 两者都列出

        Returns:
            日期列表字典
        """
        try:
            result = {
                "success": True,
            }

            # 本地日期
            if source in ("local", "both"):
                local_dates = self._get_local_dates()
                result["local"] = {
                    "dates": local_dates,
                    "count": len(local_dates),
                    "earliest": local_dates[-1] if local_dates else None,
                    "latest": local_dates[0] if local_dates else None,
                }

            # 远程日期（已禁用）
            if source in ("remote", "both"):
                result["remote"] = {
                    "configured": False,
                    "dates": [],
                    "count": 0,
                    "earliest": None,
                    "latest": None,
                    "message": "远程存储功能已禁用"
                }

            return result

        except MCPError as e:
            return {
                "success": False,
                "error": e.to_dict()
            }
        except Exception as e:
            return {
                "success": False,
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": str(e)
                }
            }
