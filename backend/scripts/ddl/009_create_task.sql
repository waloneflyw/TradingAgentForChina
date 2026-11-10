-- 009 · 任务/调度状态 + 选股候选池

-- task_id 是字符串（后端生成 UUID），与 SSE 订阅路径 /api/analysis/{task_id}/stream 一致，
-- analysis_report.task_id / analysis_trace.task_id / message.task_id 统一引用它。
CREATE TABLE IF NOT EXISTS task (
    task_id         VARCHAR(64)  NOT NULL COMMENT '任务 id（UUID）',
    type            VARCHAR(16)  NOT NULL COMMENT 'analysis/screener',
    user_id         BIGINT UNSIGNED NULL COMMENT '所属用户',
    conversation_id BIGINT UNSIGNED NULL COMMENT '所属会话',
    stock_code      VARCHAR(10)  NULL COMMENT '股票代码（analysis 用，screener 可空）',
    status          VARCHAR(16)  NOT NULL DEFAULT 'pending' COMMENT 'pending/running/success/failed',
    input_json      JSON         NULL COMMENT '入参',
    result_json     JSON         NULL COMMENT '结果摘要',
    error_msg       TEXT         NULL COMMENT '失败信息',
    created_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    started_at      DATETIME     NULL,
    finished_at     DATETIME     NULL,
    PRIMARY KEY (task_id),
    KEY idx_user_created (user_id, created_at),
    KEY idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='任务/调度状态';

CREATE TABLE IF NOT EXISTS screener_pool (
    id          BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    task_id     VARCHAR(64) NOT NULL COMMENT '选股任务 id',
    stock_code  VARCHAR(10) NOT NULL COMMENT '代码',
    stock_name  VARCHAR(64) NULL COMMENT '名称',
    hit_tags    JSON        NULL COMMENT '命中的标签数组',
    metrics     JSON        NULL COMMENT '快照：现价/涨跌幅/PE/PB/ROE/命中标签数',
    create_time DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_task (task_id),
    KEY idx_stock (stock_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='选股候选池（量化初筛结果）';
