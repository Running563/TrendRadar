-- TrendRadar 统一数据库表结构 (v5.1)
-- 合并热榜和 RSS 数据到单一数据库
-- 配置存储到数据库，不支持直接修改配置文件

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
-- 存储所有配置项，value 使用 JSON 格式
-- ============================================
CREATE TABLE IF NOT EXISTS app_config (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    description TEXT DEFAULT '',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================
-- RSS 源配置表
-- ============================================
CREATE TABLE IF NOT EXISTS rss_feeds (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    url TEXT NOT NULL,
    enabled INTEGER DEFAULT 1,
    max_age_days INTEGER DEFAULT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================
-- 通知渠道配置表
-- ============================================
CREATE TABLE IF NOT EXISTS notification_channels (
    channel TEXT PRIMARY KEY,
    enabled INTEGER DEFAULT 0,
    config TEXT NOT NULL DEFAULT '{}',
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

-- ============================================
-- 初始化默认配置（如果不存在）
-- ============================================
INSERT OR IGNORE INTO app_config (key, value, description) VALUES
    ('app.timezone', '"Asia/Shanghai"', '时区配置'),
    ('app.show_version_update', 'true', '显示版本更新提示'),
    ('report.mode', '"current"', '报告模式: daily | current | incremental'),
    ('report.rank_threshold', '5', '排名高亮阈值'),
    ('report.sort_by_position_first', 'false', '按配置位置排序'),
    ('report.max_news_per_keyword', '0', '每个关键词最大显示数量'),
    ('report.reverse_content_order', 'false', '热点词汇统计在前'),
    ('rss.enabled', 'true', 'RSS 抓取开关'),
    ('rss.freshness_filter.enabled', 'true', '新鲜度过滤开关'),
    ('rss.freshness_filter.max_age_days', '3', '最大文章年龄(天)'),
    ('notification.enabled', 'false', '通知功能开关'),
    ('notification.push_window.enabled', 'false', '推送时间窗口开关'),
    ('notification.push_window.start', '"20:00"', '推送窗口开始时间'),
    ('notification.push_window.end', '"22:00"', '推送窗口结束时间'),
    ('notification.push_window.once_per_day', 'true', '每天只推送一次'),
    ('storage.data_dir', '"data"', '数据目录'),
    ('storage.retention_days', '0', '数据保留天数'),
    ('storage.formats.sqlite', 'true', '启用 SQLite 存储'),
    ('storage.formats.txt', 'false', '启用 TXT 快照'),
    ('advanced.crawler.enabled', 'true', '爬虫开关'),
    ('advanced.crawler.request_interval', '1000', '请求间隔(毫秒)'),
    ('advanced.crawler.use_proxy', 'false', '爬虫代理开关'),
    ('advanced.crawler.default_proxy', '""', '爬虫默认代理地址'),
    ('advanced.rss.request_interval', '2000', 'RSS 请求间隔(毫秒)'),
    ('advanced.rss.timeout', '15', 'RSS 请求超时(秒)'),
    ('advanced.rss.use_proxy', 'false', 'RSS 代理开关'),
    ('advanced.rss.proxy_url', '""', 'RSS 代理地址'),
    ('advanced.rss.notification_enabled', 'true', 'RSS 通知推送开关'),
    ('advanced.weight.rank', '0.6', '排名权重'),
    ('advanced.weight.frequency', '0.3', '频次权重'),
    ('advanced.weight.hotness', '0.1', '热度权重'),
    ('advanced.max_accounts_per_channel', '3', '每个渠道最大账号数'),
    ('advanced.batch_send_interval', '3', '批次发送间隔(秒)'),
    ('advanced.batch_size.default', '4000', '默认批次大小'),
    ('advanced.batch_size.dingtalk', '20000', '钉钉批次大小'),
    ('advanced.batch_size.feishu', '29000', '飞书批次大小'),
    ('advanced.batch_size.bark', '3600', 'Bark批次大小'),
    ('advanced.batch_size.slack', '4000', 'Slack批次大小'),
    ('advanced.feishu_message_separator', '"━━━━━━━━━━━━━━━━━━━"', '飞书消息分隔符'),
    ('advanced.version_check_url', '"https://raw.githubusercontent.com/example/TrendRadar/master/version"', '版本检查URL');

-- ============================================
-- 初始化默认平台（如果不存在）
-- ============================================
INSERT OR IGNORE INTO platforms (id, name, type, is_active) VALUES
    ('toutiao', '今日头条', 'hotlist', 1),
    ('baidu', '百度热搜', 'hotlist', 1),
    ('wallstreetcn-hot', '华尔街见闻', 'hotlist', 1),
    ('thepaper', '澎湃新闻', 'hotlist', 1),
    ('bilibili-hot-search', 'bilibili 热搜', 'hotlist', 1),
    ('cls-hot', '财联社热门', 'hotlist', 1),
    ('ifeng', '凤凰网', 'hotlist', 1),
    ('tieba', '贴吧', 'hotlist', 1),
    ('weibo', '微博', 'hotlist', 1),
    ('douyin', '抖音', 'hotlist', 1),
    ('zhihu', '知乎', 'hotlist', 1);

-- ============================================
-- 初始化默认 RSS 源（如果不存在）
-- ============================================
INSERT OR IGNORE INTO rss_feeds (id, name, url, enabled) VALUES
    ('hacker-news', 'Hacker News', 'https://hnrss.org/frontpage', 1),
    ('ruanyifeng', '阮一峰的网络日志', 'http://www.ruanyifeng.com/blog/atom.xml', 1);

-- ============================================
-- 初始化默认通知渠道（如果不存在）
-- ============================================
INSERT OR IGNORE INTO notification_channels (channel, enabled, config) VALUES
    ('feishu', 0, '{"webhook_url": ""}'),
    ('dingtalk', 0, '{"webhook_url": ""}'),
    ('wework', 0, '{"webhook_url": "", "msg_type": "markdown"}'),
    ('telegram', 0, '{"bot_token": "", "chat_id": ""}'),
    ('ntfy', 0, '{"server_url": "https://ntfy.sh", "topic": "", "token": ""}'),
    ('bark', 0, '{"url": ""}'),
    ('slack', 0, '{"webhook_url": ""}');
