-- 008 · 会话 + 消息（对话记忆持久化 + 前端分页翻看历史）

CREATE TABLE IF NOT EXISTS conversation (
    id         BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    user_id    BIGINT UNSIGNED NOT NULL COMMENT '所属用户',
    title      VARCHAR(256) NULL COMMENT '会话标题（首条消息或自动摘要）',
    pref_json  JSON         NULL COMMENT '会话级偏好（可选，覆盖用户级）',
    created_at DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_user_updated (user_id, updated_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='会话';

CREATE TABLE IF NOT EXISTS message (
    id              BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    conversation_id BIGINT UNSIGNED NOT NULL COMMENT '所属会话',
    role            VARCHAR(16) NOT NULL COMMENT 'user/assistant/system',
    msg_type        VARCHAR(32) NOT NULL DEFAULT 'text' COMMENT 'text/task_card/report_card/system',
    content         TEXT        NOT NULL COMMENT '消息正文（Markdown）',
    task_id         VARCHAR(64) NULL COMMENT '关联任务（任务卡）',
    report_id       BIGINT UNSIGNED NULL COMMENT '关联报告（报告卡）',
    created_at      DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_conv_id (conversation_id, id),
    KEY idx_task (task_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='消息';
