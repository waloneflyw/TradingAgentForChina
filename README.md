# TradingAgentForChina · A股多智能体分析服务

将开源项目 [TradingAgents](https://github.com/TauricResearch/TradingAgents) 的「多智能体投研辩论」框架移植到 A 股，构建一个**实用、可部署、自带前端可视化**的个股分析 / 选股 / 金融问答服务。

- 后端：Python + LangGraph 多智能体编排 + FastAPI（SSE 流式）
- 前端：Vite + Vue3 + TypeScript + ECharts
- 数据：MySQL（`fastapi_db` 只读源库 → `ashare_agent` 业务库）+ QMT / akshare 数据管道

## 核心特性

对应立项时的三项硬性要求：

1. **自有前端可视化** — K 线 / 技术指标图、多智能体分析流程可视化、结构化分析报告展示（`frontend/`）。
2. **可部署到服务器** — 前后端分离，后端 6~7 个 REST/SSE 端点，前端 `vite build` 产出静态资源，详见 [部署与局域网访问.md](docs/部署与局域网访问.md)。
3. **实用** — 覆盖单股深度分析、条件选股、金融助手问答三条业务线，分析结果（报告 / 追踪 / 对话）落库可回溯。

## 系统架构

```
QMT(miniQMT) / akshare / 巨潮
        │  数据管道 scripts/pipeline/*
        ▼
   ashare_agent (MySQL)
        │  app/tools 9 个查询工具（本地库优先 → 源拉取兜底）
        ▼
LangGraph 多智能体（分析师 / 研究员 / 交易员 / 风控）
        │
        ▼
FastAPI (app/api) ── SSE 流式 ──► Vue3 前端
```

多智能体编排：`backend/app/agents/`（`analysts` 分析师、`researchers` 研究员、`trader` 交易员、`risk_mgmt` 风控、`managers` 经理）、`backend/app/graph/trading_graph.py`（辩论 / 信号传播图）。

## 已实现阶段

| 阶段 | 内容 | 状态 |
|---|---|---|
| 0 | 数据库基座（建库建表 + `daily_bar` 迁移 + 复权因子） | ✅ |
| 1 | 数据管道（财务三表 / 公告 / 新闻 / 申万行业 / 快照增量落库） | ✅ |
| 2 | 数据层替换（A股版 9 工具 + 路由） | ✅ |
| 3 | 多智能体编排（单股 / 选股 / 助手三 agent） | ✅ |
| 4 | FastAPI + SSE（分析 / 选股 / 对话端点 + 落库） | ✅ |
| 4.5 | 金融助手（`retrieve_history` + `chat/stream` + 合规护栏） | ✅ |
| 5 | Vue3 前端（聊天 / 三层工作台 / 选股 / K 线） | ✅ |
| 6 | QMT 日线补齐 + 每日定时落库 | ✅ |
| 7 | 全历史回填（平安银行等深历史缺口）、服务器部署联调 | ⏳ |

## 目录结构

```
TradingAgentForChina/
├── backend/              # FastAPI 后端 + 数据管道 + 多智能体
│   ├── app/              # 生产代码（api / agents / graph / tools / dataflows / db / llm_clients）
│   ├── scripts/          # ddl / migrate / pipeline（一次性与定时脚本）
│   ├── tests/            # 迁移与复权因子正确性测试
│   ├── .env.example      # 环境变量模板（复制为 .env 填真实值）
│   └── README.md         # 后端分阶段详细说明（数据源 / 工具 / 脚本用法）
├── frontend/             # Vue3 + ECharts 前端
├── docs/                 # 操作文档（部署与局域网访问、异步并发教学）
├── 需求分析/             # 需求背景 / 实现思路 / 前端 PRD
└── README.md             # 本文件
```

## 快速开始

### 0. 前置条件

- **两个 Python 环境**（本机约定）：
  - `D:\py\python.exe`（3.12.8）—— 具备 `xtquant` + `pymysql` + `sqlalchemy` + `pandas`，用于**阶段 0 迁移**与 **QMT 日线管道**；
  - `tradingagents` conda 环境 —— 具备 `akshare` + `fastapi` + `uvicorn` + `langgraph`，用于**数据管道 / agent / API**。
- **MySQL**：存在 `fastapi_db`（只读源库，**严禁写**）与 `ashare_agent`（业务库，唯一写入目标）。
- **miniQMT**：`127.0.0.1:58610`，需客户端启动并登录（拉复权因子 / 日线时在线）。
- **DeepSeek API Key**（写入 `.env`，不提交）。

### 1. 后端配置

```bash
cd backend
cp .env.example .env      # 填入 DB_PASSWORD、DEEPSEEK_API_KEY 等真实值
```

`.env` 已被 `.gitignore` 排除，切勿提交。

### 2. 初始化数据库

```bash
# 迁移日线 + 回填复权因子 + 建表（详见 backend/README.md）
D:/py/python.exe scripts/migrate/migrate_daily_bar.py
D:/py/python.exe scripts/migrate/backfill_adj_factor.py
D:/py/python.exe scripts/ddl/run_ddl.py
```

### 3. 启动后端

```bash
cd backend
# 用 tradingagents 环境
python run_server.py      # 或 uvicorn app.api.main:app
```

### 4. 启动前端

```bash
cd frontend
npm install
npm run dev               # 开发；npm run build 产出 dist/ 用于部署
```

## QMT 日线管道与定时任务

`daily_bar` 的每日增量已落地为 QMT 管道，解决「历史缺口 + 无每日调度」两类问题：

```bash
# 增量补齐到今天（每只股票从库内最新交易日的次日补起，幂等 upsert）
D:/py/python.exe backend/scripts/pipeline/qmt_backfill_daily.py

# 强制从某日重拉覆盖（修历史缺口）
D:/py/python.exe backend/scripts/pipeline/qmt_backfill_daily.py --start 20260901
```

- **定时任务**：`backend/scripts/pipeline/register_qmt_daily_task.bat`（以管理员运行）注册 Windows 计划任务 `AStockAgent-DailyBar`，周一至周五 16:30 执行 `run_qmt_daily.bat` 做增量更新，日志写入 `backend/logs/qmt_daily_update.log`。
- 复权因子沿用 dr 事件算法：`adj_factor(t) = 1 / ∏(dr_i | 除权日 > t)`（规避 xtquant `front/none` 对送转股的负价 bug）。

## 安全与合规说明

- **`fastapi_db` 只读**：任何脚本不得写入源库，业务数据只写入 `ashare_agent`（经 `target_conn`）。
- **密钥不入库**：MySQL 密码、DeepSeek API Key 一律写入 `backend/.env`（已 gitignore），代码中不硬编码。
- 金融助手内置合规护栏（免责声明、拒绝荐股 / 预测点位等），见 `backend/app/api/compliance.py`。

## 文档索引

- [backend/README.md](backend/README.md) — 分阶段实现细节、数据源适配、9 工具与脚本用法
- [docs/部署与局域网访问.md](docs/部署与局域网访问.md) — 服务器部署 / 局域网访问
- [需求分析/](需求分析/) — 需求背景、整体实现思路、前端 PRD、交接摘要
