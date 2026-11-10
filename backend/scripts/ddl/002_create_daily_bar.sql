-- =============================================================
-- 阶段 0 · A股日线表（不复权）+ 前复权因子
-- 源：fastapi_db.market_daily（只读），新增列 adj_factor。
--
-- 复权语义：
--   前复权价 = 不复权价 × adj_factor（最新交易日 adj_factor = 1）
--   后复权价 = 不复权价 × adj_factor / MIN(adj_factor)
--   adj_factor 为 NULL 时按 1 处理（等价于不复权）。
-- =============================================================
CREATE TABLE IF NOT EXISTS `daily_bar` (
  `id`            BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '自增主键',
  `stock_code`    VARCHAR(10)     NOT NULL COMMENT '股票代码，如 600025.SH',
  `trade_date`    DATE            NOT NULL COMMENT '交易日',
  `open`          DECIMAL(12,4)   DEFAULT NULL COMMENT '开盘价(不复权)',
  `high`          DECIMAL(12,4)   DEFAULT NULL COMMENT '最高价(不复权)',
  `low`           DECIMAL(12,4)   DEFAULT NULL COMMENT '最低价(不复权)',
  `close`         DECIMAL(12,4)   DEFAULT NULL COMMENT '收盘价(不复权)',
  `pre_close`     DECIMAL(12,4)   DEFAULT NULL COMMENT '昨收价(不复权)',
  `pct_chg`       DECIMAL(10,4)   DEFAULT NULL COMMENT '涨跌幅(%)',
  `amplitude`     DECIMAL(10,4)   DEFAULT NULL COMMENT '振幅(%)',
  `volume`        BIGINT          DEFAULT NULL COMMENT '成交量(手，×100=股)',
  `amount`        DECIMAL(16,2)   DEFAULT NULL COMMENT '成交额(元)',
  `turnover_rate` DECIMAL(12,4)   DEFAULT NULL COMMENT '换手率(%)',
  `adj_factor`    DECIMAL(20,8)   DEFAULT NULL COMMENT '前复权因子(前复权价=不复权价×因子；最新交易日=1；NULL按1处理)',
  `suspend_flag`  TINYINT         NOT NULL DEFAULT 0 COMMENT '停牌标志 0=正常 1=停牌',
  `create_time`   DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `update_time`   DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_stock_date` (`stock_code`, `trade_date`),
  KEY `idx_trade_date` (`trade_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='A股日线(不复权)+前复权因子';
