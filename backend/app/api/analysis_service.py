# -*- coding: utf-8 -*-
"""单股分析的 SSE 流式服务。

【并发模型】经典「asyncio.Queue + 后台线程」：
  - 端点是 async 生成器，从 asyncio.Queue 里取事件吐 SSE；
  - worker 线程跑同步的 graph.stream（LLM 调用阻塞），用 loop.call_soon_threadsafe
    把事件塞进队列（asyncio.Queue 非线程安全，必须经 loop 中转）。

【事件来源】自定义 AgentCallbackHandler：
  - on_chain_start/end 捕 12 个 agent 节点（node 事件）；
  - on_tool_start/end 捕工具调用（tool 事件）；
  - 四份分析师报告用 stream_mode="values" 快照里 *_report 非空判断（report 事件）。

【落库】worker 线程内同步写：analysis_report 最终一份 + analysis_trace 每条事件即时插。
"""
from __future__ import annotations

from typing import Any, Callable, Dict, Optional

from langchain_core.callbacks import BaseCallbackHandler

from app.api import store
from app.api.deps import get_graph

# 12 个 agent 节点名（与 app/graph/setup.py 里 add_node 的名字精确一致）
AGENT_NODES = {
    "Market Analyst",
    "Social Analyst",
    "News Analyst",
    "Fundamentals Analyst",
    "Bull Researcher",
    "Bear Researcher",
    "Research Manager",
    "Trader",
    "Aggressive Analyst",
    "Neutral Analyst",
    "Conservative Analyst",
    "Portfolio Manager",
}

# 四份报告对应的 state 字段 → 前端展示名（按流水线出现顺序）
REPORT_FIELDS = {
    "market_report": "技术面",
    "sentiment_report": "情绪面",
    "news_report": "新闻面",
    "fundamentals_report": "基本面",
}

# 合规护栏 ②：报告模板固定免责声明（头部/尾部通用，落库 + 前端均可见）
DISCLAIMER = "本报告由 AI 自动生成，仅供信息参考，不构成任何投资建议；股市有风险，入市需谨慎。"


class AgentCallbackHandler(BaseCallbackHandler):
    """把 LangGraph 运行中的节点/工具事件转成结构化回调。

    注意 LangGraph 的 on_chain_end 拿不到节点名（只有 run_id），
    所以靠 on_chain_start 记录 run_id → 节点名 的映射来回查。

    工具事件额外带上「归属分析师」：每个分析师的工具节点名是 tools_{analyst}，
    工具运行在该节点内，靠 on_tool_start 的 parent_run_id 沿父链向上回查到
    这个 tools_* 节点，再映射回分析师名（供前端「分析路程图」把工具归到对应 agent）。
    """

    def __init__(self, on_node: Callable, on_tool: Callable):
        self.on_node = on_node  # (phase: start|end, name) -> None
        self.on_tool = on_tool  # (phase: call|result, name, detail, node) -> None
        self._node_by_run: Dict[str, str] = {}       # agent 节点 run_id → 节点名
        self._tool_node_by_run: Dict[str, str] = {}  # tools_{x} 节点 run_id → 分析师名
        self._parent_by_run: Dict[str, str] = {}     # 任意 run_id → parent_run_id
        self._tool_by_run: Dict[str, tuple] = {}     # 工具 run_id → (工具名, 归属分析师)

    def on_chain_start(self, serialized, inputs, *, run_id, parent_run_id=None, tags=None, metadata=None, **kwargs):
        name = kwargs.get("name")
        self._parent_by_run[run_id] = parent_run_id
        if name in AGENT_NODES:
            self._node_by_run[run_id] = name
            self.on_node("start", name)
        elif name and name.startswith("tools_"):
            analyst_type = name[len("tools_"):]  # market / social / news / fundamentals
            self._tool_node_by_run[run_id] = f"{analyst_type.capitalize()} Analyst"

    def on_chain_end(self, outputs, *, run_id, parent_run_id=None, **kwargs):
        name = self._node_by_run.pop(run_id, None)
        if name:
            self.on_node("end", name)
        self._tool_node_by_run.pop(run_id, None)
        self._parent_by_run.pop(run_id, None)

    def _resolve_node(self, parent_run_id: str) -> Optional[str]:
        """沿父链向上回查工具归属的分析师（工具运行在 tools_{x} 节点内）。"""
        cur = parent_run_id
        while cur:
            if cur in self._tool_node_by_run:
                return self._tool_node_by_run[cur]
            if cur in self._node_by_run:
                return self._node_by_run[cur]
            cur = self._parent_by_run.get(cur)
        return None

    def on_tool_start(self, serialized, input_str, *, run_id, parent_run_id=None, tags=None, metadata=None, inputs=None, **kwargs):
        name = (serialized or {}).get("name") or "unknown_tool"
        node = self._resolve_node(parent_run_id)
        self._tool_by_run[run_id] = (name, node)
        self.on_tool("call", name, str(input_str)[:200], node)

    def on_tool_end(self, output, *, run_id, parent_run_id=None, **kwargs):
        name, node = self._tool_by_run.pop(run_id, (kwargs.get("name") or "unknown_tool", None))
        detail = str(output)[:300] if output is not None else ""
        self.on_tool("result", name, detail, node)


def _build_report_json(final_state: Dict[str, Any], rating: str) -> Dict[str, Any]:
    """把最终状态里对外有用的字段抽成报告全文，并在结论末尾强制追加免责声明。"""
    decision = final_state.get("final_trade_decision", "") or ""
    if DISCLAIMER not in decision:
        decision = f"{decision.rstrip()}\n\n{DISCLAIMER}"
    return {
        "company_of_interest": final_state.get("company_of_interest"),
        "trade_date": final_state.get("trade_date"),
        "market_report": final_state.get("market_report", ""),
        "sentiment_report": final_state.get("sentiment_report", ""),
        "news_report": final_state.get("news_report", ""),
        "fundamentals_report": final_state.get("fundamentals_report", ""),
        "investment_plan": final_state.get("investment_plan", ""),
        "trader_investment_plan": final_state.get("trader_investment_plan", ""),
        "final_trade_decision": decision,
        "disclaimer": DISCLAIMER,
        "rating": rating,
    }


def run_analysis_sync(
    code: str,
    analysis_date: str,
    task_id: str,
    emit: Callable[[Dict[str, Any]], None],
) -> Dict[str, Any]:
    """worker 线程体：跑完整分析，边跑边发 node/tool/report 事件 + 落报告。阻塞、同步。

    只发进度事件（node/tool/report），**不发** done/error（终态事件由调用方决定），
    而是把结果 return 出来，异常则 raise。这样 /api/analysis 和金融助手的
    run_stock_analysis 都能复用：前者包 done/error，后者拿返回值回填给 LLM。

    Args:
        emit: 事件回调（端点层实现，把事件塞进 asyncio 队列）。

    Returns:
        {rating, summary, decision, stock_name, industry} —— 供调用方拼终态/回填。
    """
    seq_counter = {"n": 0}

    def _trace(event_type: str, node_name: str, summary=None) -> None:
        seq_counter["n"] += 1
        store.save_trace(task_id, seq_counter["n"], node_name, event_type, summary)

    def on_node(phase: str, name: str) -> None:
        emit({"type": "node", "name": name, "phase": phase})
        _trace("node_start" if phase == "start" else "node_end", name)

    def on_tool(phase: str, name: str, detail: str, node: Optional[str]) -> None:
        ev: Dict[str, Any] = {"type": "tool", "name": name, "phase": phase, "detail": detail}
        if node:
            ev["node"] = node
        emit(ev)
        _trace(
            "tool_call" if phase == "call" else "tool_result",
            name,
            {"args": detail, "node": node} if phase == "call" else {"result": detail, "node": node},
        )

    graph = get_graph()
    handler = AgentCallbackHandler(on_node, on_tool)

    init_state = graph.propagator.create_initial_state(code, analysis_date)
    args = graph.propagator.get_graph_args(callbacks=[handler])

    emitted_reports = set()
    final_state = None
    try:
        for chunk in graph.graph.stream(init_state, **args):
            final_state = chunk
            # 报告字段从空串变非空 → 该分析师写完了，发 report 事件
            for field, label in REPORT_FIELDS.items():
                if field not in emitted_reports and chunk.get(field):
                    emitted_reports.add(field)
                    emit({"type": "report", "analyst": label, "report": chunk[field]})
                    _trace("llm_output", field, {"analyst": label})
    except Exception as e:  # 图运行异常：抛给调用方，由调用方决定发 error 还是回填
        raise RuntimeError(f"分析失败：{e}") from e

    if final_state is None:
        raise RuntimeError("分析未产出任何状态（图为空）")

    rating = graph.process_signal(final_state["final_trade_decision"])
    report_json = _build_report_json(final_state, rating)
    name, industry = store.lookup_stock(code)
    summary = (final_state.get("final_trade_decision") or "")[:500]

    store.save_report(task_id, code, name, industry, rating, analysis_date, summary, report_json)

    return {
        "rating": rating,
        "summary": summary,
        "decision": report_json["final_trade_decision"],
        "stock_name": name,
        "industry": industry,
    }
