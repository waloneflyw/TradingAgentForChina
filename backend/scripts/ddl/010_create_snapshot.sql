-- 010 · 每日横截面快照（千股千评 + 人气榜，选股初筛因子）

-- 数据源：akshare 东财。stock_comment_em 千股千评（全市场，含综合得分/关注指数/排名/市盈率），
-- stock_hot_rank_em 人气榜（top N，稀疏，未上榜为 NULL）。
-- 唯一键 (trade_date, stock_code)：同一交易日重复拉取覆盖更新（幂等）。
CREATE TABLE IF NOT EXISTS stock_snapshot (
    trade_date                DATE         NOT NULL COMMENT '快照交易日（千股千评「交易日」）',
    stock_code                VARCHAR(10)  NOT NULL COMMENT '股票代码（后缀 600519.SH）',
    stock_name                VARCHAR(64)  NULL COMMENT '名称',
    latest_price              DECIMAL(20,4) NULL COMMENT '最新价',
    pct_change                DECIMAL(12,4) NULL COMMENT '涨跌幅（%）',
    turnover_rate             DECIMAL(12,4) NULL COMMENT '换手率（%）',
    pe                        DECIMAL(20,4) NULL COMMENT '市盈率（千股千评口径，负数为亏损）',
    main_cost                 DECIMAL(20,4) NULL COMMENT '主力成本',
    institution_participation DECIMAL(12,4) NULL COMMENT '机构参与度',
    composite_score           DECIMAL(12,4) NULL COMMENT '综合得分',
    score_change              DECIMAL(12,4) NULL COMMENT '综合得分较昨日变化（上升/下降点数，可负）',
    comment_rank              INT          NULL COMMENT '目前排名（千股千评）',
    attention_index           DECIMAL(12,4) NULL COMMENT '关注指数',
    hot_rank                  INT          NULL COMMENT '人气榜排名（未上榜 NULL）',
    hot_value                 DECIMAL(20,4) NULL COMMENT '人气榜热度值（未上榜 NULL）',
    PRIMARY KEY (trade_date, stock_code),
    KEY idx_stock_date (stock_code, trade_date),
    KEY idx_rank (trade_date, comment_rank)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='每日横截面快照（千股千评+人气榜，选股初筛因子）';
