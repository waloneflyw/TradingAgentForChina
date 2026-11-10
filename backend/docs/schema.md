# ashare_agent 库 · 表结构设计（阶段 0）

> 配套 DDL 脚本在 `scripts/ddl/`（001 建库、002 daily_bar、003~009 本阶段其余表）。
> 约定：utf8mb4 / utf8mb4_0900_ai_ci / InnoDB；**不用 FOREIGN KEY 约束**，靠列 + 索引做逻辑关联
> （便于数据管道增量 upsert，避免外键在部分写入时的连锁报错）。复权因子语义见 README。

## 表清单

| DDL | 表 | 用途 | 唯一键 |
|---|---|---|---|
| 002 | `daily_bar` | 日线 + 前复权因子（已建） | (stock_code, trade_date) |
| 003 | `stock_info` | 基础信息：行业/板块/上市日/ST/pinyin | stock_code(PK) |
| 004 | `financial_statement` | 三大报表竖表 | (stock_code, report_date, report_type, item_name) |
| 004 | `financial_indicator` | PE/PB/ROE/增速（选股初筛因子） | (stock_code, report_date) |
| 005 | `news` | 新闻舆情（情绪打分现算不落库） | (source, url) |
| 005 | `announcement` | 公告列表（正文按需解析） | url |
| 006 | `analysis_report` | 分析报告全文 + 检索元数据 | task_id |
| 006 | `analysis_trace` | agent 过程结构化摘要（回放用） | (task_id, seq) |
| 007 | `user` | 用户 + 偏好记忆 | username |
| 007 | `watchlist` | 自选股 | (user_id, stock_code) |
| 008 | `conversation` | 会话 | id |
| 008 | `message` | 消息（分页翻看） | id |
| 009 | `task` | 任务/调度状态 | task_id(PK) |
| 009 | `screener_pool` | 选股候选池（量化初筛结果） | id |
| 010 | `stock_snapshot` | 每日横截面快照（千股千评+人气榜，选股初筛因子） | (trade_date, stock_code) |

> `memory`（经验记忆）按 MVP 收敛已移除，留 L3。

## 关键设计决策

1. **stock_info 数据来源**：一次性只读拷贝 `fastapi_db.stocks`（code/name/pinyin/market/status），
   再 enrichment：`list_date`（QMT）、`industry_sw_l1/l2`（akshare 申万）、`boards`（东财概念板块，JSON 数组）、
   `is_st`（由 name 的 `*ST` 前缀判）。之后彻底不再碰 fastapi_db。
2. **三大报表 = 竖表**：`financial_statement` 用 `report_type + item_name + value`，任意报表行通吃、
   可 SQL 聚合、季度增量幂等。`financial_indicator` 单独结构化列，供选股初筛「纯 SQL」直接 WHERE。
3. **情绪打分、技术指标不落库**（现算）：`news`/`announcement` 只存原始内容，情绪由 LLM 运行时算；
   技术指标由 `daily_bar` 用 stockstats 现算。
4. **trace 分层**：`analysis_trace` 只存结构化摘要（节点生命周期/工具调用名+入参+返回摘要+数据来源标注），
   **不存工具返回原文、不存即时流 token**（回放靠 `seq` 顺序重建）。
5. **报告检索元数据**：`analysis_report` 带 `stock_code/stock_name/industry/board/rating/analysis_date`
   结构化列（供「全局知识库 / 历史报告引用」检索），报告全文走 `report_json` JSON 列。
6. **task_id 是字符串**（后端生成 UUID），`task`/`analysis_report`/`analysis_trace`/`message` 统一引用，
   与 SSE 订阅路径 `/api/analysis/{task_id}/stream` 一致。

## 落库 vs 运行时（四问标准）

✅ 落库（管道定时增量）：daily_bar、stock_info、financial_*、announcement、news、screener_pool
⚡ 运行时获取：盘中实时价/盘口（QMT）；冷门缺失时现场拉一次并落库
🚫 不落库：技术指标（现算）、情绪打分（现算）

## 阶段 1 管道已知缺口

- **list_date 老股偏差**：`000001.SZ`/`000002.SZ` 等少数老股在 `daily_bar` 仅 15 天历史
  （源 `market_daily` 缺口），`MIN(trade_date)` 算出的上市日偏晚。待历史回补后重算。
- **financial_indicator 估值列 NULL**：`pe/pb/dividend_yield/total_market_cap` 现为 NULL，
  估值逐日变化不宜进「报告期」粒度表，留给后续「每日估值快照」任务。
- **申万行业 enrichment 源限流**：legulegu 对 335 次批量抓取限流，脚本已 `retries=1` 快速失败 +
  `.sw_cache.json` 增量续跑，需错峰重跑至失败数为 0。
- **daily_bar 时效**：`market_daily` 迁移的历史数据截至 2026-09-04，无每日增量调度前行情滞后，
  运行时由 `kline.fill_missing_daily` 按需 akshare 补齐（见阶段 2）。
- **financial_indicator 全市场未回填**：目前仅样例股落库，选股初筛（get_stock_screener）的
  ROE/成长类条件在全市场回填前命中有限。

