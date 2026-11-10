-- 005 · 新闻 + 公告
-- 情绪打分现算不落库（LLM 运行时算），这里只存原始内容，靠 (source, url) 去重。

CREATE TABLE IF NOT EXISTS news (
    id           BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    stock_code   VARCHAR(10)  NULL COMMENT '关联个股（全市场快讯可空）',
    source       VARCHAR(32)  NOT NULL COMMENT '来源：cls/akshare/eastmoney/...',
    url          VARCHAR(512) NOT NULL COMMENT '原文链接（去重键）',
    title        VARCHAR(512) NOT NULL COMMENT '标题',
    content      MEDIUMTEXT   NULL COMMENT '正文',
    publish_time DATETIME     NOT NULL COMMENT '发布时间',
    create_time  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_source_url (source, url),
    KEY idx_stock_time (stock_code, publish_time),
    KEY idx_publish_time (publish_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='新闻舆情（情绪现算）';

CREATE TABLE IF NOT EXISTS announcement (
    id            BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    stock_code    VARCHAR(10)  NOT NULL COMMENT '代码',
    title         VARCHAR(512) NOT NULL COMMENT '公告标题',
    url           VARCHAR(512) NOT NULL COMMENT '公告链接（去重键）',
    announce_time DATETIME     NOT NULL COMMENT '公告时间（毫秒时间戳转 Asia/Shanghai）',
    category      VARCHAR(64)  NULL COMMENT '公告类别',
    content       MEDIUMTEXT   NULL COMMENT '正文（按需解析，可空）',
    create_time   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_url (url),
    KEY idx_stock_time (stock_code, announce_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='公告列表';
