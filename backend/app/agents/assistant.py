# -*- coding: utf-8 -*-
"""金融助手对话 agent —— 外层 router。

【角色】把「个股深度分析」和「量化选股」两个子流程包成工具，再加上日常问答的
轻量工具（search_stock / get_quote / get_market_overview），用一个带合规人格的
router 统一承接用户自然语言。

【它调用的 5 个工具】
  - search_stock        按名称/代码/拼音查股票（日常问答）
  - get_quote           查最新行情快照（日常问答）
  - get_market_overview 看大盘指数/板块/北向（日常问答）
  - run_stock_analysis  跑 11-agent 单股分析（重，返回评级 + 结论摘要）
  - run_screener        跑量化选股初筛（重，返回候选池）

【router 的循环】和 screener.py 一样是「手动工具循环」：LLM 决定要调哪个工具 →
执行 → 看结果 → 继续，直到它给出最终回答。区别是这里工具更多、且两个重工具
会进程内调用子图（本阶段无 SSE，阶段 4 报告落库后再接 get_report）。

【合规人格】system 提示内置红线：不承诺收益、不预测点位、不构成投资建议。
"""
from __future__ import annotations

import contextvars
from datetime import date
from typing import Annotated, Any, Callable, Dict, List, Optional

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool

from app.tools.assistant_tools import get_quote, retrieve_history, search_stock
from app.tools.stock_tools import get_market_overview

MAX_TOOL_ITERATIONS = 12

# 流式对话时，worker 线程用它把「调用同事」过程事件透传给重工具。
# 仅 /api/chat/stream 会 set；/api/chat 保持 None → 走进程内同步老路径。
_emit_ctx: contextvars.ContextVar = contextvars.ContextVar("assistant_emit", default=None)


def set_emit(emit: Optional[Callable[[Dict[str, Any]], None]]) -> None:
    """worker 线程内设置 emit 回调，让 run_stock_analysis/run_screener 冒泡进度事件。"""
    _emit_ctx.set(emit)

# ---- 懒加载的重工具依赖（进程内单例，避免每次对话重建 11-agent 图）----
_analysis_graph = None
_screener_agent = None


def _get_analysis_graph():
    global _analysis_graph
    if _analysis_graph is None:
        from app.graph import TradingAgentsGraph
        _analysis_graph = TradingAgentsGraph()
    return _analysis_graph


def _get_screener_agent():
    global _screener_agent
    if _screener_agent is None:
        from app.llm_clients import create_llm_client
        from app.config import Config
        from app.agents.screener import create_screener_agent
        llm = create_llm_client(
            provider=Config.LLM_PROVIDER,
            model=Config.QUICK_THINK_LLM,
            base_url=Config.BACKEND_URL,
        ).get_llm()
        _screener_agent = create_screener_agent(llm)
    return _screener_agent


@tool
def run_stock_analysis(
    symbol: Annotated[str, "股票代码，如 600519.SH"],
    analysis_date: Annotated[str, "分析基准日期 yyyy-mm-dd"],
) -> str:
    """对某只 A股做深度研究分析（技术/基本面/新闻/情绪多维分析 + 多空辩论 + 风控），
    返回五档评级（买/增持/持有/减持/卖）与结论摘要。耗时较长（约 1-3 分钟），
    仅当用户明确要求「分析某只股票」时才调用，日常问答不要调用。
    """
    emit = _emit_ctx.get()
    if emit is not None:  # 流式路径：冒泡「调用同事」+ 子图事件 + 落报告
        from uuid import uuid4

        from app.api.analysis_service import run_analysis_sync

        task_id = uuid4().hex[:16]
        emit({"type": "colleague", "name": "run_stock_analysis", "phase": "start", "detail": symbol})
        try:
            result = run_analysis_sync(symbol, analysis_date, task_id, emit)
            emit({"type": "colleague", "name": "run_stock_analysis", "phase": "end",
                  "detail": f"评级 {result['rating']}",
                  "task_id": task_id, "rating": result["rating"]})
            return f"评级：{result['rating']}\n\n{result['decision']}"
        except Exception as e:  # 分析失败也要回填给 LLM，别让 router 卡死
            emit({"type": "colleague", "name": "run_stock_analysis", "phase": "error", "detail": str(e)})
            return f"分析失败：{e}"

    # 非流式兜底：进程内同步跑（无 SSE、不落报告）
    final_state, rating = _get_analysis_graph().propagate(symbol, analysis_date)
    decision = final_state["final_trade_decision"]
    return f"评级：{rating}\n\n{decision}"


@tool
def run_screener(
    query: Annotated[str, "选股条件（自然语言），如 新能源、PE<30、ROE>10"],
) -> str:
    """按自然语言条件做 A股量化初筛，返回候选池总结（代码/名称/ROE/PE/增速等）。

    仅当用户表达「选股/筛选/找一批股票」意图时调用。
    """
    emit = _emit_ctx.get()
    if emit is not None:
        emit({"type": "colleague", "name": "run_screener", "phase": "start", "detail": query})
        try:
            result = _get_screener_agent()(query)
            emit({"type": "colleague", "name": "run_screener", "phase": "end", "detail": "候选池已生成"})
            return result
        except Exception as e:
            emit({"type": "colleague", "name": "run_screener", "phase": "error", "detail": str(e)})
            return f"选股失败：{e}"
    return _get_screener_agent()(query)


SYSTEM_TEMPLATE = """你是「A股智研助手」，面向个人投资者的 A股研究助手。你的能力：

1. 日常问答：解释金融概念、市场规则、个股/板块基本面。用工具直接查：
   - search_stock(keyword)   按名称/代码/拼音查股票代码
   - get_quote(ticker)       查最新行情快照（现价/涨跌幅/PE/换手/关注度）
   - get_market_overview(date) 看大盘指数/板块/北向资金
   - retrieve_history(stock_code, industry) 查本服务曾跑出的历史分析报告（用户问
     「你之前分析过 X 吗 / 上次评级如何 / 历史结论」时用，传代码或行业名）
2. 个股深度分析：用户明确要求「分析/研究某只股票」时，调用
   run_stock_analysis(symbol, analysis_date) 做深度研究分析，返回五档评级。
3. 量化选股：用户描述「选股/筛选/找一批」条件时，调用 run_screener(query) 返回候选池。

工作原则：
- 用户没明确要深度分析或选股时，用轻量工具（search_stock/get_quote/get_market_overview）
  直接回答，**不要擅自跑耗时很长的 run_stock_analysis**。
- 拿到工具返回后要如实转述，不编造数据；数据缺失就明说。

你的团队（内部视角，用于自然转述，不要向用户说这是「AI/模型/程序」）：
- 个股深度分析由一支分析师团队完成：技术面 / 情绪面 / 新闻面 / 基本面四位分析师分别研究，
  随后牛方、熊方两位研究员辩论，研究经理汇总，交易员拟交易计划，激进派 / 中性派 / 保守派
  三位风控师把关，最终由组合经理给出五档评级（买/增持/持有/减持/卖）。
- 量化选股由选股团队做初筛，产出候选池。

口吻与表达（务必遵守）：
- 你就是这支团队的负责人/代言人，用第一人称复数「我们」、亲近自然的语气说话，
  例如「我让我们的分析师团队为您做深度分析」「我们的技术面分析师认为…」
  「我们的激进派分析师更谨慎一些」；选股同理，可说「我们的选股团队帮您筛了一遍」。
- 多提「我们」「我们团队」，让用户感受到是一支团队在服务；不要以一个孤零零的「我」
  冷冰冰地自述，也不要自称「我是一个 AI / 模型 / 程序」。
- 结论直接给出即可，不必逐条复述「我调了哪些工具/步骤」（过程会由界面自动展示）。

合规红线（必须遵守）：
- 回答涉及投资判断时，末尾必须提示「以上不构成投资建议，据此操作风险自担」；
- 不推荐具体买卖时点、仓位与杠杆/配资；涉及 ST、退市风险、高波动题材时主动提示风险。

今天的日期是 {today}。请用中文回答。"""


def _execute_tool_calls(result, tools_by_name: Dict[str, Any]) -> List[ToolMessage]:
    """执行 LLM 这一轮请求的所有工具调用，把每个结果包装成 ToolMessage 回填。"""
    tool_messages = []
    for tc in result.tool_calls:
        fn = tools_by_name[tc["name"]]
        observation = fn.invoke(tc["args"])
        tool_messages.append(
            ToolMessage(content=str(observation), tool_call_id=tc["id"], name=tc["name"])
        )
    return tool_messages


def _text_of(content) -> str:
    """把流式 chunk 的 content 归一化成字符串（兼容 list 分块 / 空值）。"""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and item.get("type") == "text":
                parts.append(item.get("text", ""))
        return "".join(parts)
    return str(content)


def create_assistant_agent(
    llm,
    history: Optional[List] = None,
    system_hint: str = "",
    on_delta: Optional[Callable[[str], None]] = None,
) -> Callable[[str], str]:
    """返回一个 chat(message) 函数：内部维护多轮对话历史，输入用户消息，返回助手回复。

    Args:
        history: 可选的历史消息种子（langchain 消息列表，如从 DB 回填的 user/assistant
                 文本）。缺省则从空历史开始。system 提示由本函数统一加在最前。
        system_hint: 可选的一轮性合规提示（如命中敏感词时的「转回免责话术」），
                 追加在 system 提示末尾，不进历史种子。
    """

    tools = [
        search_stock,
        get_quote,
        get_market_overview,
        retrieve_history,
        run_stock_analysis,
        run_screener,
    ]
    llm_with_tools = llm.bind_tools(tools)
    tools_by_name = {t.name: t for t in tools}

    system = SYSTEM_TEMPLATE.format(today=date.today().isoformat())
    if system_hint:
        system += "\n\n【额外合规提示】" + system_hint

    messages: List[Any] = [SystemMessage(content=system)]
    if history:
        messages.extend(history)

    def chat(message: str) -> str:
        messages.append(HumanMessage(content=message))

        for _ in range(MAX_TOOL_ITERATIONS):
            if on_delta is not None:
                # 流式：逐 token 产出最终回答。工具调用轮 content 为空（模型只回 tool_calls），
                # 所以「中间思考」不会泄漏给前端，只有最终回答会逐字推送。
                result = None
                for chunk in llm_with_tools.stream(messages):
                    delta = _text_of(chunk.content)
                    if delta:
                        on_delta(delta)
                    result = chunk if result is None else (result + chunk)
                if result is not None:
                    result.content = _text_of(result.content)
            else:
                result = llm_with_tools.invoke(messages)

            messages.append(result)

            if not result.tool_calls:
                return result.content

            messages.extend(_execute_tool_calls(result, tools_by_name))

        return result.content

    return chat
