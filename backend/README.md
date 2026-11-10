# backend · 阶段 0（数据库基座）+ 阶段 1（数据管道）

## 目录结构

- `app/` 主代码（生产代码）：`config.py` 配置、`db/` 连接工具、`dataflows/` 数据源适配层
- `tests/` 测试：验证迁移与复权因子正确性
- `scripts/` 一次性脚本（不属于运行时）：`ddl/` 建库建表、`migrate/` 迁移+回填、`pipeline/` 阶段 1 数据管道
- `.env` 本地配置（含密码，不提交）；`.env.example` 模板；`.gitignore` 排除敏感文件

## 环境

- 运行 Python（阶段 0 迁移）：`D:\py\python.exe`（3.12.8，同时具备 `xtquant` + `pymysql/aiomysql/sqlalchemy/pandas`）
- 运行 Python（阶段 1 数据管道）：`tradingagents` conda 环境（含 `akshare` + `pymysql` + `cryptography`）
- 数据源：`fastapi_db`（**只读，严禁写**）；目标库：`ashare_agent`（唯一写入目标）
- miniQMT：`127.0.0.1:58610`（回填复权因子时需在线）

## 复权因子（adj_factor）语义

- 定义：`adj_factor = 前复权收盘价 / 不复权收盘价`，最新交易日 = 1，越往历史越小。
- 推导：
  - 前复权价 = 不复权价 × adj_factor
  - 后复权价 = 不复权价 × adj_factor / MIN(adj_factor)
  - adj_factor 为 NULL 按 1 处理（等价于不复权）。
- 算法：用 xtquant `get_divid_factors` 的每次除权事件复权因子 `dr`（恒正的乘法因子）：
  `adj_factor(t) = 1 / ∏(dr_i | 除权日 > t)`。
  **为什么不用 `get_market_data_ex` 的 front/none 相除**：那对「送转股」会算出负数
  （如贵州茅台 10转10 后 front 价累积失真为负，实测 2001 年 front=-312）。
  `dr` 事件算法是标准复权因子算法（tushare 的 adj_factor 同源），且只需稀疏事件，
  比下载全套日线快几个数量级。
- **不变量与例外**：普通分红/送转股满足 `0 < adj_factor <= 1`。但「缩股」（反向拆股，
  dr<1）会抬高历史价，故 `adj_factor > 1` 是**合法**的——全库仅 4 只缩股股出现因子 >1：
  `000156.SZ` / `000722.SZ` / `600094.SH` / `600381.SH`（后者 2014 年约 8:1 并股，
  因子最大 8.05 = 1/0.124179）。另有 8 只有 dr<1 但被后续送转对冲、因子仍 ≤1。

## 一次性脚本（按序执行）

```bash
# 1) 迁移日线（建库建表 + fastapi_db.market_daily → ashare_agent.daily_bar）
D:/py/python.exe scripts/migrate/migrate_daily_bar.py

# 2) 回填复权因子（先小批验证，再全量）
D:/py/python.exe scripts/migrate/backfill_adj_factor.py --codes 600025.SH,000001.SZ,600519.SH
D:/py/python.exe scripts/migrate/backfill_adj_factor.py          # 全量，去掉 --codes/--limit

# 3) 建其余 13 张表（幂等，可重复跑；001~009）
D:/py/python.exe scripts/ddl/run_ddl.py

# 4) 验证
D:/py/python.exe tests/test_daily_bar.py
```

## 表清单（阶段 0 全部建成）

`daily_bar` + 13 张新表：`stock_info` / `financial_statement`（竖表）/
`financial_indicator` / `news` / `announcement` / `analysis_report` /
`analysis_trace` / `user` / `watchlist` / `conversation` / `message` /
`task` / `screener_pool`。字段/索引/唯一键设计见 [docs/schema.md](docs/schema.md)。

- `stock_info`：一次性只读拷 `fastapi_db.stocks` 再 enrichment（上市日 QMT、申万行业/概念板块 akshare、is_st）
- `financial_*`：三大报表竖表 + 指标结构化列（选股初筛 SQL 用）
- `analysis_report`：报告全文 JSON + 检索元数据（stock_code/industry/board/rating/date）
- `analysis_trace`：只存结构化摘要（节点/工具调用/数据来源），不存工具原文
- 情绪打分、技术指标**不落库**（现算）；`memory`（经验记忆）MVP 移除

## 后续

阶段 1 数据管道：把 QMT/akshare 数据增量落库到上述表（财务三表/指标、公告、新闻、
申万行业、股票基础信息），先跑通「一只股票全链路落库 + 幂等」。

---

# 阶段 1 · 数据管道（QMT/akshare → 各表增量落库）

## 数据源适配层（`app/dataflows/`）

| 模块 | 职责 |
|---|---|
| `symbols.py` | 代码格式转换：裸码 ↔ `600519.SH` 后缀 ↔ `SH600519` 前缀（财务三表用前缀，财务指标用后缀，落库统一后缀） |
| `akshare_source.py` | 统一 akshare 封装：`call()`（重试+节流+退避）、`require()`（`dir()` 自检接口存在性），静音内部 tqdm |
| `financial_map.py` | 三大报表英文列名→中文科目名映射、指标列映射（EPS/ROE/ROA/增速/毛利率/净利率） |
| `db_writer.py` | 通用 `upsert()`：`INSERT ... ON DUPLICATE KEY UPDATE`，NaN/Inf→NULL、dict/list→JSON |
| `cninfo.py` | 巨潮公告直连：`org_id()`（深市 szse_stock.json + topSearch 兜底，不可推导）+ 分页查询 + ms 时间戳→Asia/Shanghai |
| `sw_industry.py` | 申万行业反向索引：三级成分股 →（申万一级/二级），带缓存可续跑 |

## 管道脚本（`scripts/pipeline/`，用 tradingagents 环境跑）

```bash
cd backend
PY="C:/Users/24167/.conda/envs/tradingagents/python.exe"

# 1) 股票基础信息：拷 fastapi_db.stocks + 增补 list_date/is_st（无外部 API，快）
$PY scripts/pipeline/stock_info_fill.py

# 2) 财务三表竖表 + 财务指标（东财，逐股）
$PY scripts/pipeline/financial_fill.py --codes 600519.SH,000001.SZ,300750.SZ

# 3) 公告列表（巨潮 cninfo，逐股，近 2 年）
$PY scripts/pipeline/announcement_fill.py --codes 600519.SH,000001.SZ

# 4) 新闻：财联社电报（全市场）+ 东财个股新闻兜底
$PY scripts/pipeline/news_fill.py                          # 只拉财联社
$PY scripts/pipeline/news_fill.py --codes 600519.SH        # 追加个股新闻

# 5) 申万行业 enrichment（约 335 次接口，多线程 + .sw_cache.json 增量续跑）
$PY scripts/pipeline/stock_info_fill.py --sw

# 6) 每日横截面快照：千股千评（全市场）+ 人气榜（best-effort）→ stock_snapshot
$PY scripts/pipeline/snapshot_fill.py

# 7) 验收：样例股全链路落库两遍，对比各表行数（幂等校验）
$PY scripts/pipeline/run_sample.py --codes 600519.SH,000001.SZ,300750.SZ
```

## 幂等设计

- 所有写入走 `ON DUPLICATE KEY UPDATE`，按各表唯一键 upsert：
  `stock_info(stock_code)`、`financial_statement(stock_code, report_date, report_type, item_name)`、
  `financial_indicator(stock_code, report_date)`、`announcement(url)`、`news(source, url)`。
- 已验证：`run_sample.py` 连跑两遍，各表行数一致（PASS）。

## 已知缺口（需后续处理）

1. **list_date 对少数老股不准**：`000001.SZ`（平安银行）/`000002.SZ`（万科A）在 `daily_bar`
   仅 15 天历史（源 `market_daily` 缺口），导致 `MIN(trade_date)` 算出的上市日偏晚
   （2026-08 而非 1991）。约 208 只有 `list_date >= 2024`，含真·次新股与历史不全混在一起。
   后续可用 QMT 全量日线或东财复权价回补历史后重算。
2. **financial_indicator 估值列留空**：`pe/pb/dividend_yield/total_market_cap` 现为 NULL
   （估值逐日变化，不适合进「报告期」粒度表），留给后续「每日估值快照」任务。
3. **申万行业 enrichment 依赖源错峰**：legulegu 对 335 次批量抓取会限流（返回空表 / ValueError /
   AttributeError），脚本已设 `retries=1` 快速失败 + `.sw_cache.json` 增量续跑，
   建议夜间/错峰重跑直至失败数为 0。单个 `sw_index_third_cons` 调用本身已验证可用。

---

# 阶段 2 · 数据层替换（A股版 tools + route）

## 架构（对应参考项目 dataflows/interface.py 的「薄壳 → 路由 → 供应商」三层）

```
app/tools/stock_tools.py    @tool 薄壳（9 个，供阶段 3 分析师绑定）
        ↓ route(method, ...)
app/dataflows/interface.py  A股版路由：method → 实现函数 分发表
        ↓
app/dataflows/*.py          实现层（本地库优先 → akshare 缺则拉 + 落库）
```

- 美股版在多供应商（yfinance/alpha_vantage）间回退；A股版是「本地库优先 → 源拉取兜底 +
  落库」单一路径，故路由简化为一张分发表。
- 复权语义：工具返回**前复权** OHLCV（前复权价 = 不复权价 × `daily_bar.adj_factor`）。

## 9 个工具（文档阶段 2 清单）

| 工具 | 数据来源 | 落库/运行时 |
|---|---|---|
| `get_stock_data` | `daily_bar`（缺则 akshare `stock_zh_a_hist` 拉+落库）；周/月线日线聚合 | 落库 |
| `get_indicators` | `daily_bar` 前复权 K线 + stockstats 现算 | 现算 |
| `get_fundamentals` | stock_info + financial_indicator + stock_snapshot | 落库 |
| `get_financial_statements` | `financial_statement` 竖表 pivot 宽表 | 落库 |
| `get_news` | `news` 表（缺则东财 `stock_news_em` 拉+落库） | 落库 |
| `get_announcements` | `announcement` 表（缺则巨潮 cninfo 拉+落库） | 落库 |
| `get_shareholder_changes` | 东财高管增减持 `stock_ggcg_em` + 龙虎榜 `stock_lhb_detail_em` | 运行时 |
| `get_market_overview` | 指数 `stock_zh_index_spot_em` + 板块 + 北向 `stock_hsgt_*` | 运行时 |
| `get_stock_screener` | 纯 SQL join stock_info/financial_indicator/stock_snapshot | 落库 |

## 验收（`scripts/verify_tools.py`）

```bash
$PY scripts/verify_tools.py     # 逐个调用 9 工具，PASS/FAIL/SKIP
```

- 核心查库类工具（K线/指标/基本面/财报/新闻/公告/选股）应全 PASS。
- 运行时拉取类（大盘/股东/龙虎榜）受东财限流，失败记为 SKIP，错峰重跑即可。
- 已实测 9/9 工具返回正确 A股数据（含前复权），「查库→缺则拉→落库」兜底生效
  （源限流时优雅降级为「无数据」而非崩溃）。

## 阶段 2 已知限制

1. **运行时拉取受东财限流**：`stock_ggcg_em`/`stock_lhb_detail_em`/指数/板块/北向等接口
   高频调用会 ConnectionError，脚本已 `retries=1` 快速失败 + 优雅降级。
2. **选股初筛依赖全市场数据**：`get_stock_screener` 的 ROE/成长类条件靠 `financial_indicator`，
   目前仅样例股回填，全市场回填前命中有限。
3. **daily_bar 增量未调度**：`market_daily` 历史截至 2026-09-04，`kline.fill_missing_daily`
   提供按需补齐机制，但「每日增量落库」的定时调度属阶段 7。
