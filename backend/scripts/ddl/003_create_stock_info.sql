-- 003 · stock_info 股票基础信息
-- 数据来源：一次性只读拷贝 fastapi_db.stocks（code/name/pinyin/market/status），
-- 再 enrichment：list_date(QMT) / industry_sw_l1/l2(akshare申万) / boards(东财概念板块) / is_st(name前缀)。
CREATE TABLE IF NOT EXISTS stock_info (
    id             BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    stock_code     VARCHAR(10)  NOT NULL COMMENT '代码，如 600519.SH',
    name           VARCHAR(64)  NOT NULL COMMENT '名称',
    pinyin         VARCHAR(128) NOT NULL DEFAULT '' COMMENT '拼音（供 search_stock 联想）',
    market         VARCHAR(10)  NOT NULL DEFAULT '' COMMENT 'SH_A/SZ_A/GEM/STAR',
    status         VARCHAR(10)  NOT NULL DEFAULT 'LISTED' COMMENT 'LISTED/DELISTED',
    list_date      DATE         NULL COMMENT '上市日（QMT）',
    industry_sw_l1 VARCHAR(64)  NULL COMMENT '申万一级行业',
    industry_sw_l2 VARCHAR(64)  NULL COMMENT '申万二级行业',
    boards         JSON         NULL COMMENT '概念板块数组（东财），如 ["AI","机器人"]',
    is_st          TINYINT      NOT NULL DEFAULT 0 COMMENT '是否 ST/*ST（由 name 前缀判）',
    create_time    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    update_time    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_code (stock_code),
    KEY idx_industry (industry_sw_l1, industry_sw_l2),
    KEY idx_market (market),
    KEY idx_is_st (is_st)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='股票基础信息';
