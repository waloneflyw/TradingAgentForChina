# -*- coding: utf-8 -*-
"""构造图运行的「初始状态」与「运行参数」。

【作用】LangGraph 的图需要一个初始状态字典才能启动。本文件负责：
  1. create_initial_state() —— 把「股票代码 + 日期」包装成完整初始状态
  2. get_graph_args()      —— 返回运行参数（重点是 recursion_limit）

【为什么 recursion_limit 很重要】
  多空辩论和风控辩论会反复经过同一批节点（循环），LangGraph 默认把
  「同一节点被执行次数」的上限设得很低，一旦超限就报错、误判为死循环。
  所以这里把 limit 设大（100），保证辩论循环能正常跑完。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.agents.utils.agent_states import (
    AgentState,
    InvestDebateState,
    RiskDebateState,
)


class Propagator:
    """Handles state initialization and propagation through the graph."""

    def __init__(self, max_recur_limit=100):
        """Initialize with configuration parameters."""
        self.max_recur_limit = max_recur_limit

    def create_initial_state(
        self, company_name: str, trade_date: str
    ) -> Dict[str, Any]:
        """Create the initial state for the agent graph.

        【状态初始值】所有「报告类」字段都是空字符串，两个「辩论状态」都把
        count 归零、历史置空——图会在运行过程中逐步填充它们。
        """
        return {
            # 第一条消息就是股票代码本身，作为整场分析的「问题输入」
            "messages": [("human", company_name)],
            "company_of_interest": company_name,
            "trade_date": str(trade_date),
            "investment_debate_state": InvestDebateState(
                {
                    "bull_history": "",
                    "bear_history": "",
                    "history": "",
                    "current_response": "",
                    "judge_decision": "",
                    "count": 0,
                }
            ),
            "risk_debate_state": RiskDebateState(
                {
                    "aggressive_history": "",
                    "conservative_history": "",
                    "neutral_history": "",
                    "history": "",
                    "latest_speaker": "",
                    "current_aggressive_response": "",
                    "current_conservative_response": "",
                    "current_neutral_response": "",
                    "judge_decision": "",
                    "count": 0,
                }
            ),
            "market_report": "",
            "fundamentals_report": "",
            "sentiment_report": "",
            "news_report": "",
        }

    def get_graph_args(self, callbacks: Optional[List] = None) -> Dict[str, Any]:
        """Get arguments for the graph invocation.

        Args:
            callbacks: Optional list of callback handlers for tool execution tracking.
                       Note: LLM callbacks are handled separately via LLM constructor.
        """
        config = {"recursion_limit": self.max_recur_limit}
        if callbacks:
            config["callbacks"] = callbacks
        return {
            # stream_mode="values"：让 debug 模式下能拿到每一步的完整状态快照
            "stream_mode": "values",
            "config": config,
        }
