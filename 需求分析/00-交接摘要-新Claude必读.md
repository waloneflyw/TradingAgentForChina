# 交接摘要 · 新 Claude 必读

> 给在 `D:\AgentFrame\TradingAgentForChina` 新工作区开工的 Claude。
> 这是上个工作区（`D:\AgentFrame\TradingAgents`）积累的关键上下文浓缩版，请先读本文件，再读同文件夹的 `00-需求背景与可行性分析.md`（更全的展开）。

---

## 0. 你是谁、要做什么

- 用户在开发一个**面向 A股的多智能体分析服务**（新项目，路径 `D:\AgentFrame\TradingAgentForChina`）。
- **参考/复用源码在 `D:\AgentFrame\TradingAgents`**（TradingAgents 开源项目，已跑通：DeepSeek + AAPL 出 Buy 结论）。
- **开工前先读这份 TradingAgents 代码**，重点文件见 §4；它是「复用 vs 替换」的基准（doc §6 有逐模块对照表）。
- 硬目标：① 有自己的前端可视化；② 能部署到服务器；③ **实用而非 demo**。

## 1. 已拍板决策（不要重议，除非用户主动改）

| 决策项 | 结论 |
|---|---|
| MVP 边界 | 只做「个股深度分析 + 标签选股」 |
| 选股范围 | 全市场 5000+（沪深 A股） |
| 交易 | 只做分析建议，不接真实下单 |
| 数据源 | QMT/xtquant 为主 + akshare 兜底 |
| 服务形态 | 独立新服务，暂只读 fastapi_db，后续自建新库（如 `ashare_agent`） |
| 前端 | Vue3 + ECharts（K线/指标）+ 自绘流程图 |
| 实时推流 | SSE（**硬性要求**：展示 agent 思考过程 + 数据来源 + 报告，doc §12） |
| 持久化 | MVP 全 MySQL JSON 列；落库 vs 运行时获取标准见 doc §11 |
| 选股架构 | 「量化初筛 → LLM 精析」两层漏斗（全市场用 SQL 初筛，不逐只 LLM 扫） |

## 2. 实测验证过的环境事实（不用再试，直接采信）

**三个 Python（跑脚本前先选对）**
- `C:\Users\24167\.conda\envs\tradingagents\python.exe` —— 项目主环境，有 akshare 1.18.94 / requests / pandas / langchain
- `D:\py\python.exe` —— Python 3.12.8，**只有 xtquant**（QMT SDK），无 akshare
- `C:\ProgramData\anaconda3\python.exe` —— conda base，无 akshare

**MySQL 8.0.46 `fastapi_db`（只读查看，严禁改）**
- `market_daily`：1573 万行、5218 只、1992-2026 日线；字段 open/high/low/close/preClose/pct_chg/volume/amount/...；⚠️ **无复权因子**；⚠️ volume 单位「手」；代码格式 `600025.SH`。
- `stocks`：code/name/market(SH_A/SZ_A/GEM/STAR)/pinyin/status；ST 靠 name 里的 `*ST` 前缀。

**QMT / xtquant（已连通）**
- miniQMT 模式已跑通（`127.0.0.1:58610`）。
- ⚠️ 取历史 K线前必须先 `xtdata.download_history_data(代码, '1d', 起, 止)` 再 `get_market_data_ex`，否则返回空。
- 复权 none/front/back 都验证可用（`dividend_type` 参数），正好补 market_daily 缺的复权。

**情报源可行性（实测，doc §13 + `D:\AgentFrame\TradingAgents\爬虫测试\`）**
- ✅ 可行：财报三表/财务指标（akshare 东财）、巨潮公告（直连 cninfo）、财联社快讯（直连+sign）、千股千评/人气榜（akshare）、龙虎榜/北向/申万（akshare 接口齐全）。
- ❌ 缺口：**个股股吧帖子** akshare 无现成接口，MVP 建议降级用千股千评/人气榜代替散户情绪。

## 3. 关键坑（务必记住）

- **中文 Windows 控制台 GBK**：任何 €/emoji/→ 字符会让 print() 崩 → 入口脚本加 `sys.stdout.reconfigure(encoding="utf-8", errors="replace")`，写文件加 `encoding="utf-8"`。
- **akshare 接口名随版本变**：`stock_a_indicator_lg`、`stock_guba_em`、`stock_telegraph_cls` 在当前版本已消失 → 生产必须 `dir()` 自检 + 版本锁定。
- **symbol 格式不统一**：财务指标用 `600025.SH`（后缀），三大报表用 `SH600025`（前缀）。
- **巨潮公告**：orgId 要查 `http://www.cninfo.com.cn/new/data/szse_stock.json` 映射表；A股 column=`szse`（不是 `sse`）；公告时间是毫秒时间戳需转 Asia/Shanghai。
- **财联社**：接口是 `v1/roll/get_roll_list`，要 `sign=md5(sha1(urlencode(params)))` 签名。
- **复权含义**：前复权=技术指标/看图（当前价不变、历史价下调）；后复权=算真实收益率。

## 4. TradingAgents 代码里要先读的文件（复用基准）

- `graph/setup.py` —— 11 个 agent 的 StateGraph 流水线（**最值得精读**，边/条件边/工具循环/消息清理机制都在这里）
- `agents/analysts/*.py` —— 4 个分析师（「工具型 agent」的标准写法，可照抄结构改 A股 prompt）
- `agents/utils/agent_states.py` —— AgentState（共享 messages + 各报告字段）
- `agents/utils/agent_utils.py` —— `get_language_instruction`（中文输出）、`create_msg_delete`（清消息）
- `agents/utils/*_tools.py` —— 数据工具（**要替换成 A股版**：get_stock_data/get_indicators/get_fundamentals/get_news）
- `agents/utils/memory.py` + `graph/reflection.py` —— 记忆/反思机制（BM25 情境→教训，可复用，中文效果待验证）
- `cli/main.py` —— 入口 + 配置（output_language 等）
- `dataflows/` —— yfinance/alpha_vantage 数据层（**要替换成 QMT/akshare/MySQL**）

**复用 vs 替换完整对照表：doc §6。**

## 5. 安全约束（严格遵守）

- **严禁私自修改 `fastapi_db` 数据库内容，只授权查看**（MySQL 密码不在此摘要，需向用户要）。
- **不要 echo DeepSeek API key**（在 `.env` 里）。

## 6. 文档结构（`00-需求背景与可行性分析.md` 的章节地图）

- §1 背景目标 / §2 现状盘点 / §2.5 已拍板决策 / §2.6 akshare实测 / §2.7 MySQL+QMT实测 / §2.8 复权+xtquant
- §3 功能 brainstorm（L1个股分析 / L2标签选股 / L3组合监控回测 / L4工程化）
- §4 数据源 / §5 新闻舆情 / §6 复用vs替换 / §7 工具清单 / §8 指标筛选（两层漏斗）
- §9 关键决策分叉 / §10 待验证条件 / §11 持久化+落库标准 / §12 前端+流程可视化（SSE+Vue3）/ §13 情报源可行性实测

---

**给新 Claude 的行动清单**：①读本摘要；②读 TradingAgents 代码（§4 文件）；③通读需求分析 doc；④和用户确认下一步（建议从「新库 schema」或「数据管道」开始）。
