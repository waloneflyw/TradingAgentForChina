-- 006 · 分析产物：报告全文 + 过程 trace

-- analysis_report：报告全文走 JSON 列；检索元数据提为结构化列供「全局知识库 / 历史报告引用」。
CREATE TABLE IF NOT EXISTS analysis_report (
    id              BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    task_id         VARCHAR(64)  NOT NULL COMMENT '任务 id（与 task.task_id 一致）',
    user_id         BIGINT UNSIGNED NULL COMMENT '所属用户',
    conversation_id BIGINT UNSIGNED NULL COMMENT '所属会话',
    stock_code      VARCHAR(10)  NOT NULL COMMENT '股票代码',
    stock_name      VARCHAR(64)  NULL COMMENT '股票名称',
    industry        VARCHAR(64)  NULL COMMENT '申万一级（检索元数据）',
    board           VARCHAR(128) NULL COMMENT '板块（检索元数据）',
    rating          VARCHAR(20)  NULL COMMENT 'buy/overweight/hold/underweight/sell',
    analysis_date   DATE         NOT NULL COMMENT '分析日期',
    summary         TEXT         NULL COMMENT '结论摘要',
    report_json     JSON         NULL COMMENT '全文：各分析师报告 + 最终评级 + 理由',
    create_time     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_task (task_id),
    KEY idx_stock_date (stock_code, analysis_date),
    KEY idx_industry (industry),
    KEY idx_rating (rating),
    KEY idx_user (user_id),
    KEY idx_conversation (conversation_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='分析报告（全文 JSON + 检索元数据）';

-- analysis_trace：只存结构化摘要（节点生命周期/工具调用名+入参+返回摘要+数据来源标注），
-- 不存工具返回原文、不存即时流 token；断线重连按 (task_id, seq) 顺序回放重建。
CREATE TABLE IF NOT EXISTS analysis_trace (
    id          BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    task_id     VARCHAR(64)  NOT NULL COMMENT '任务 id',
    seq         INT          NOT NULL COMMENT '事件序号（回放顺序）',
    node_name   VARCHAR(64)  NULL COMMENT '所属 agent/节点',
    event_type  VARCHAR(32)  NOT NULL COMMENT 'node_start/node_end/tool_call/tool_result/llm_output',
    summary     JSON         NULL COMMENT '结构化摘要：入参/返回摘要/来源/耗时/token',
    create_time DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_task_seq (task_id, seq),
    KEY idx_task (task_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='agent 过程 trace（结构化摘要）';
