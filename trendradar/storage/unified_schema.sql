-- TrendRadar 统一数据库表结构 (v5.0)
-- 合并热榜和 RSS 数据到单一数据库

-- ============================================
-- 平台信息表
-- ============================================
CREATE TABLE IF NOT EXISTS platforms (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    type TEXT DEFAULT 'hotlist' CHECK(type IN ('hotlist', 'rss')),
    is_active INTEGER DEFAULT 1,
    feed_url TEXT DEFAULT '',
    last_fetch_time TEXT,
    last_fetch_status TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================
-- 新闻条目表 (合并热榜和RSS)
-- ============================================
CREATE TABLE IF NOT EXISTS news_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    platform_id TEXT NOT NULL,
    rank INTEGER DEFAULT 0,
    url TEXT DEFAULT '',
    mobile_url TEXT DEFAULT '',
    summary TEXT DEFAULT '',
    author TEXT DEFAULT '',
    published_at TEXT,
    first_crawl_time TEXT NOT NULL,
    last_crawl_time TEXT NOT NULL,
    crawl_count INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (platform_id) REFERENCES platforms(id)
);

-- ============================================
-- 标题变更历史表
-- ============================================
CREATE TABLE IF NOT EXISTS title_changes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    news_item_id INTEGER NOT NULL,
    old_title TEXT NOT NULL,
    new_title TEXT NOT NULL,
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (news_item_id) REFERENCES news_items(id)
);

-- ============================================
-- 排名历史表
-- ============================================
CREATE TABLE IF NOT EXISTS rank_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    news_item_id INTEGER NOT NULL,
    rank INTEGER NOT NULL,
    crawl_time TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (news_item_id) REFERENCES news_items(id)
);

-- ============================================
-- 抓取记录表
-- ============================================
CREATE TABLE IF NOT EXISTS crawl_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    crawl_time TEXT NOT NULL,
    crawl_type TEXT DEFAULT 'hotlist' CHECK(crawl_type IN ('hotlist', 'rss', 'all')),
    total_items INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================
-- 抓取来源状态表
-- ============================================
CREATE TABLE IF NOT EXISTS crawl_source_status (
    crawl_record_id INTEGER NOT NULL,
    platform_id TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('success', 'failed')),
    error_message TEXT,
    PRIMARY KEY (crawl_record_id, platform_id),
    FOREIGN KEY (crawl_record_id) REFERENCES crawl_records(id),
    FOREIGN KEY (platform_id) REFERENCES platforms(id)
);

-- ============================================
-- 推送记录表
-- ============================================
CREATE TABLE IF NOT EXISTS push_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    push_type TEXT DEFAULT 'hotlist' CHECK(push_type IN ('hotlist', 'rss', 'all')),
    pushed INTEGER DEFAULT 0,
    push_time TEXT,
    report_type TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(date, push_type)
);

-- ============================================
-- 应用配置表 (支持Web配置热更新)
-- ============================================
CREATE TABLE IF NOT EXISTS app_config (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================
-- 索引定义
-- ============================================
CREATE INDEX IF NOT EXISTS idx_news_platform ON news_items(platform_id);
CREATE INDEX IF NOT EXISTS idx_news_crawl_time ON news_items(last_crawl_time);
CREATE INDEX IF NOT EXISTS idx_news_title ON news_items(title);
CREATE INDEX IF NOT EXISTS idx_news_published ON news_items(published_at DESC);
CREATE UNIQUE INDEX IF NOT EXISTS idx_news_url_platform 
    ON news_items(url, platform_id) WHERE url != '';
CREATE INDEX IF NOT EXISTS idx_crawl_status_record ON crawl_source_status(crawl_record_id);
CREATE INDEX IF NOT EXISTS idx_rank_history_news ON rank_history(news_item_id);
CREATE INDEX IF NOT EXISTS idx_platforms_type ON platforms(type);
CREATE INDEX IF NOT EXISTS idx_crawl_records_type ON crawl_records(crawl_type);
