"""
TrendRadar 统一数据库管理模块
提供单一数据库的连接和操作接口
"""

import sqlite3
import os
from pathlib import Path
from typing import Optional, List, Dict, Any
from contextlib import contextmanager
from datetime import datetime

# 默认数据库路径
DEFAULT_DB_PATH = "data/trendradar.db"


def get_minute_timestamp() -> str:
    """获取分钟级别的时间戳（精确到分钟，不含秒和微秒）"""
    return datetime.now().strftime('%Y-%m-%dT%H:%M:00')


class Database:
    """统一数据库管理类"""
    
    _instance: Optional['Database'] = None
    
    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        self.db_path = db_path
        self._ensure_db_dir()
        self._init_schema()
    
    @classmethod
    def get_instance(cls, db_path: str = DEFAULT_DB_PATH) -> 'Database':
        """获取单例实例"""
        if cls._instance is None or cls._instance.db_path != db_path:
            cls._instance = cls(db_path)
        return cls._instance
    
    def _ensure_db_dir(self):
        """确保数据库目录存在"""
        db_dir = os.path.dirname(self.db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
    
    def _init_schema(self):
        """初始化数据库表结构"""
        schema_path = Path(__file__).parent / "unified_schema.sql"
        if schema_path.exists():
            with open(schema_path, 'r', encoding='utf-8') as f:
                schema_sql = f.read()
            with self.get_connection() as conn:
                conn.executescript(schema_sql)
    
    @contextmanager
    def get_connection(self):
        """获取数据库连接的上下文管理器"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    
    def execute(self, sql: str, params: tuple = ()) -> List[Dict[str, Any]]:
        """执行 SQL 并返回结果"""
        with self.get_connection() as conn:
            cursor = conn.execute(sql, params)
            if cursor.description:
                return [dict(row) for row in cursor.fetchall()]
            return []
    
    def execute_many(self, sql: str, params_list: List[tuple]) -> int:
        """批量执行 SQL"""
        with self.get_connection() as conn:
            cursor = conn.executemany(sql, params_list)
            return cursor.rowcount
    
    # ========== 平台管理 ==========
    
    def get_platforms(self, platform_type: Optional[str] = None) -> List[Dict]:
        """获取平台列表"""
        if platform_type:
            return self.execute(
                "SELECT * FROM platforms WHERE type = ? ORDER BY name",
                (platform_type,)
            )
        return self.execute("SELECT * FROM platforms ORDER BY type, name")
    
    def upsert_platform(self, platform_id: str, name: str, 
                        platform_type: str = 'hotlist',
                        feed_url: str = '', is_active: int = 1) -> None:
        """插入或更新平台"""
        self.execute("""
            INSERT INTO platforms (id, name, type, feed_url, is_active, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET 
                name = excluded.name,
                type = excluded.type,
                feed_url = excluded.feed_url,
                is_active = excluded.is_active,
                updated_at = excluded.updated_at
        """, (platform_id, name, platform_type, feed_url, is_active, 
              get_minute_timestamp()))
    
    def update_platform_status(self, platform_id: str, status: str) -> None:
        """更新平台抓取状态"""
        now = get_minute_timestamp()
        self.execute("""
            UPDATE platforms 
            SET last_fetch_time = ?, last_fetch_status = ?, updated_at = ?
            WHERE id = ?
        """, (now, status, now, platform_id))
    
    # ========== 新闻管理 ==========
    
    def get_news(self, platform_id: Optional[str] = None,
                 platform_type: Optional[str] = None,
                 date: Optional[str] = None,
                 limit: int = 100,
                 offset: int = 0,
                 search: Optional[str] = None) -> List[Dict]:
        """获取新闻列表"""
        conditions = []
        params = []
        
        if platform_id:
            conditions.append("n.platform_id = ?")
            params.append(platform_id)
        
        if platform_type:
            conditions.append("p.type = ?")
            params.append(platform_type)
        
        if date:
            conditions.append("DATE(n.first_crawl_time) = ?")
            params.append(date)
        
        if search:
            conditions.append("n.title LIKE ?")
            params.append(f"%{search}%")
        
        where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""
        
        # 时间已存储为分钟级别，直接排序即可
        sql = f"""
            SELECT n.*, p.name as platform_name, p.type as platform_type
            FROM news_items n
            JOIN platforms p ON n.platform_id = p.id
            {where_clause}
            ORDER BY COALESCE(NULLIF(n.published_at, ''), n.first_crawl_time) DESC, n.rank ASC
            LIMIT ? OFFSET ?
        """
        params.extend([limit, offset])
        
        return self.execute(sql, tuple(params))
    
    def get_news_count(self, platform_id: Optional[str] = None,
                       platform_type: Optional[str] = None,
                       date: Optional[str] = None,
                       search: Optional[str] = None) -> int:
        """获取新闻数量"""
        conditions = []
        params = []
        
        if platform_id:
            conditions.append("n.platform_id = ?")
            params.append(platform_id)
        
        if platform_type:
            conditions.append("p.type = ?")
            params.append(platform_type)
        
        if date:
            conditions.append("DATE(n.first_crawl_time) = ?")
            params.append(date)
        
        if search:
            conditions.append("n.title LIKE ?")
            params.append(f"%{search}%")
        
        where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""
        
        sql = f"""
            SELECT COUNT(*) as count
            FROM news_items n
            JOIN platforms p ON n.platform_id = p.id
            {where_clause}
        """
        
        result = self.execute(sql, tuple(params))
        return result[0]['count'] if result else 0
    
    def upsert_news(self, title: str, platform_id: str, url: str,
                    rank: int = 0, mobile_url: str = '',
                    summary: str = '', author: str = '',
                    published_at: Optional[str] = None) -> int:
        """插入或更新新闻"""
        now = get_minute_timestamp()
        
        # 先尝试查找现有记录
        existing = self.execute(
            "SELECT id, title FROM news_items WHERE url = ? AND platform_id = ?",
            (url, platform_id)
        )
        
        if existing:
            news_id = existing[0]['id']
            old_title = existing[0]['title']
            
            # 更新记录
            self.execute("""
                UPDATE news_items SET
                    title = ?, rank = ?, mobile_url = ?,
                    summary = ?, author = ?, published_at = ?,
                    last_crawl_time = ?, crawl_count = crawl_count + 1,
                    updated_at = ?
                WHERE id = ?
            """, (title, rank, mobile_url, summary, author, 
                  published_at, now, now, news_id))
            
            # 记录标题变更
            if old_title != title:
                self.execute("""
                    INSERT INTO title_changes (news_item_id, old_title, new_title)
                    VALUES (?, ?, ?)
                """, (news_id, old_title, title))
            
            # 记录排名历史
            if rank > 0:
                self.execute("""
                    INSERT INTO rank_history (news_item_id, rank, crawl_time)
                    VALUES (?, ?, ?)
                """, (news_id, rank, now))
            
            return news_id
        else:
            # 插入新记录
            self.execute("""
                INSERT INTO news_items (
                    title, platform_id, rank, url, mobile_url,
                    summary, author, published_at,
                    first_crawl_time, last_crawl_time
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (title, platform_id, rank, url, mobile_url,
                  summary, author, published_at, now, now))
            
            result = self.execute("SELECT last_insert_rowid() as id")
            news_id = result[0]['id']
            
            # 记录排名历史
            if rank > 0:
                self.execute("""
                    INSERT INTO rank_history (news_item_id, rank, crawl_time)
                    VALUES (?, ?, ?)
                """, (news_id, rank, now))
            
            return news_id
    
    def get_news_by_id(self, news_id: int) -> Optional[Dict]:
        """根据ID获取新闻详情"""
        result = self.execute("""
            SELECT n.*, p.name as platform_name, p.type as platform_type
            FROM news_items n
            JOIN platforms p ON n.platform_id = p.id
            WHERE n.id = ?
        """, (news_id,))
        return result[0] if result else None
    
    def get_rank_history(self, news_id: int) -> List[Dict]:
        """获取新闻排名历史"""
        return self.execute("""
            SELECT rank, crawl_time FROM rank_history
            WHERE news_item_id = ?
            ORDER BY crawl_time DESC
        """, (news_id,))
    
    def get_title_changes(self, news_id: int) -> List[Dict]:
        """获取新闻标题变更历史"""
        return self.execute("""
            SELECT old_title, new_title, changed_at FROM title_changes
            WHERE news_item_id = ?
            ORDER BY changed_at DESC
        """, (news_id,))
    
    # ========== 抓取记录 ==========
    
    def record_crawl(self, crawl_type: str = 'hotlist', 
                     total_items: int = 0) -> int:
        """记录一次抓取"""
        now = get_minute_timestamp()
        self.execute("""
            INSERT INTO crawl_records (crawl_time, crawl_type, total_items)
            VALUES (?, ?, ?)
        """, (now, crawl_type, total_items))
        
        result = self.execute("SELECT last_insert_rowid() as id")
        return result[0]['id']
    
    def record_crawl_status(self, crawl_record_id: int, platform_id: str,
                            status: str, error_message: str = '') -> None:
        """记录抓取状态"""
        self.execute("""
            INSERT OR REPLACE INTO crawl_source_status (crawl_record_id, platform_id, status, error_message)
            VALUES (?, ?, ?, ?)
        """, (crawl_record_id, platform_id, status, error_message))
    
    def get_crawl_records(self, limit: int = 20) -> List[Dict]:
        """获取最近的抓取记录"""
        return self.execute("""
            SELECT * FROM crawl_records
            ORDER BY crawl_time DESC
            LIMIT ?
        """, (limit,))
    
    # ========== 统计信息 ==========
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        stats = {}
        
        # 总新闻数
        result = self.execute("SELECT COUNT(*) as count FROM news_items")
        stats['total_news'] = result[0]['count']
        
        # 今日新闻数
        result = self.execute("""
            SELECT COUNT(*) as count FROM news_items 
            WHERE DATE(first_crawl_time) = DATE('now', 'localtime')
        """)
        stats['today_news'] = result[0]['count']
        
        # 各平台新闻数
        stats['platform_stats'] = self.execute("""
            SELECT p.id, p.name, p.type, COUNT(n.id) as news_count
            FROM platforms p
            LEFT JOIN news_items n ON p.id = n.platform_id
            GROUP BY p.id
            ORDER BY news_count DESC
        """)
        
        # 最近抓取时间
        result = self.execute("""
            SELECT MAX(crawl_time) as last_crawl FROM crawl_records
        """)
        stats['last_crawl'] = result[0]['last_crawl'] if result else None
        
        return stats
    
    def get_available_dates(self) -> List[str]:
        """获取有数据的日期列表"""
        result = self.execute("""
            SELECT DISTINCT DATE(first_crawl_time) as date
            FROM news_items
            ORDER BY date DESC
            LIMIT 30
        """)
        return [r['date'] for r in result]
    
    # ========== 配置管理 ==========
    
    def get_config(self, key: str) -> Optional[str]:
        """获取配置项"""
        result = self.execute(
            "SELECT value FROM app_config WHERE key = ?",
            (key,)
        )
        return result[0]['value'] if result else None
    
    def set_config(self, key: str, value: str) -> None:
        """设置配置项"""
        self.execute("""
            INSERT INTO app_config (key, value, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET 
                value = excluded.value,
                updated_at = excluded.updated_at
        """, (key, value, get_minute_timestamp()))
    
    def get_all_config(self) -> Dict[str, str]:
        """获取所有配置项"""
        result = self.execute("SELECT key, value FROM app_config")
        return {r['key']: r['value'] for r in result}
    
    # ========== 阅读状态管理 ==========
    
    def mark_news_read(self, news_id: int) -> bool:
        """标记单条新闻为已读"""
        try:
            self.execute("""
                INSERT OR REPLACE INTO news_read_status (news_id, read_at)
                VALUES (?, ?)
            """, (news_id, get_minute_timestamp()))
            return True
        except Exception:
            return False
    
    def mark_news_batch_read(self, news_ids: List[int]) -> int:
        """批量标记新闻为已读"""
        if not news_ids:
            return 0
        now = get_minute_timestamp()
        params_list = [(news_id, now) for news_id in news_ids]
        return self.execute_many("""
            INSERT OR REPLACE INTO news_read_status (news_id, read_at)
            VALUES (?, ?)
        """, params_list)
    
    def unmark_news_read(self, news_id: int) -> bool:
        """取消已读标记（恢复为未读）"""
        try:
            self.execute(
                "DELETE FROM news_read_status WHERE news_id = ?",
                (news_id,)
            )
            return True
        except Exception:
            return False
    
    def clear_read_history(self) -> int:
        """清空所有已读记录"""
        result = self.execute("SELECT COUNT(*) as count FROM news_read_status")
        count = result[0]['count'] if result else 0
        self.execute("DELETE FROM news_read_status")
        return count
    
    def get_read_news_ids(self) -> set:
        """获取所有已读新闻ID集合"""
        result = self.execute("SELECT news_id FROM news_read_status")
        return {r['news_id'] for r in result}
    
    def get_read_news_map(self) -> Dict[int, str]:
        """获取已读新闻ID到阅读时间的映射"""
        result = self.execute("SELECT news_id, read_at FROM news_read_status")
        return {r['news_id']: r['read_at'] for r in result}
    
    def get_read_stats(self, date: Optional[str] = None) -> Dict[str, int]:
        """获取阅读统计"""
        # 总已读数
        result = self.execute("SELECT COUNT(*) as count FROM news_read_status")
        read_count = result[0]['count'] if result else 0
        
        # 如果指定日期，计算该日期的未读数
        if date:
            result = self.execute("""
                SELECT COUNT(*) as count FROM news_items n
                WHERE DATE(n.first_crawl_time) = ?
                  AND n.id NOT IN (SELECT news_id FROM news_read_status)
            """, (date,))
            unread_count = result[0]['count'] if result else 0
        else:
            # 总未读数（最近7天的）
            result = self.execute("""
                SELECT COUNT(*) as count FROM news_items n
                WHERE n.first_crawl_time >= datetime('now', '-7 days')
                  AND n.id NOT IN (SELECT news_id FROM news_read_status)
            """)
            unread_count = result[0]['count'] if result else 0
        
        return {
            "unread_count": unread_count,
            "read_count": read_count
        }


# 便捷函数
def get_db(db_path: str = DEFAULT_DB_PATH) -> Database:
    """获取数据库实例"""
    return Database.get_instance(db_path)
