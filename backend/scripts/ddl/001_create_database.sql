-- =============================================================
-- 阶段 0 · 建库脚本
-- ashare_agent：自建业务库，与只读源 fastapi_db 完全隔离。
-- 约定：fastapi_db 只读（严禁写）；ashare_agent 是唯一写入目标。
-- =============================================================
CREATE DATABASE IF NOT EXISTS `ashare_agent`
  DEFAULT CHARACTER SET utf8mb4
  COLLATE utf8mb4_0900_ai_ci;
