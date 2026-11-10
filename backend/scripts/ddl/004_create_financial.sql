-- 004 · 财务数据
-- ① financial_statement：三大报表竖表（report_type + item_name + value，任意报表行通吃）
-- ② financial_indicator：估值/成长指标结构化列（供选股初筛「纯 SQL」WHERE）
-- 注意 symbol 格式：三大报表用 SH600025（前缀），指标用 600025.SH（后缀），数据管道统一转后缀存库。

CREATE TABLE IF NOT EXISTS financial_statement (
    id          BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    stock_code  VARCHAR(10)  NOT NULL COMMENT '代码，如 600519.SH',
    report_date DATE         NOT NULL COMMENT '报告期期末（如 2026-06-30）',
    report_type VARCHAR(16)  NOT NULL COMMENT 'balance/income/cashflow',
    item_name   VARCHAR(128) NOT NULL COMMENT '报表行名，如 营业总收入',
    item_value  DECIMAL(24,4) NULL COMMENT '数值（元）',
    create_time DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    update_time DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_stmt (stock_code, report_date, report_type, item_name),
    KEY idx_stock_date (stock_code, report_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='三大报表竖表';

CREATE TABLE IF NOT EXISTS financial_indicator (
    id                BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    stock_code        VARCHAR(10)  NOT NULL COMMENT '代码',
    report_date       DATE         NOT NULL COMMENT '报告期期末',
    pe                DECIMAL(16,4) NULL COMMENT '市盈率(倍)',
    pb                DECIMAL(16,4) NULL COMMENT '市净率(倍)',
    roe               DECIMAL(12,4) NULL COMMENT '净资产收益率(%)',
    roa               DECIMAL(12,4) NULL COMMENT '总资产收益率(%)',
    eps               DECIMAL(12,4) NULL COMMENT '每股收益(元)',
    revenue_growth    DECIMAL(12,4) NULL COMMENT '营收同比增速(%)',
    net_profit_growth DECIMAL(12,4) NULL COMMENT '净利同比增速(%)',
    gross_margin      DECIMAL(12,4) NULL COMMENT '毛利率(%)',
    net_margin        DECIMAL(12,4) NULL COMMENT '净利率(%)',
    dividend_yield    DECIMAL(12,4) NULL COMMENT '股息率(%)',
    total_market_cap  DECIMAL(20,2) NULL COMMENT '总市值(元)',
    create_time       DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    update_time       DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_ind (stock_code, report_date),
    KEY idx_report_date (report_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='估值/成长指标（选股初筛因子）';
