# -*- coding: utf-8 -*-
"""图里的「路口指示牌」——条件边的判断函数。

【作用】LangGraph 的 add_conditional_edges 需要一个判断函数，运行时根据当前状态
决定「下一步该跳转到哪个节点」。本文件集中放这些判断函数。

【两类判断逻辑】
  1. should_continue_*（4 个分析师）
     判断 Agent 是否还要继续调用工具：
       最后一条消息带 tool_calls → 回工具节点继续拉数据
       否则 → 报告写完了，去消息清理节点、进入下一环节

  2. should_continue_debate / should_continue_risk_analysis
     判断辩论是否该结束：靠一个 count 计数器。
       count 没到阈值 → 让下一个角色继续发言（形成循环）
       count 到阈值   → 交给「裁判」（研究经理 / 基金经理）做裁决
     阈值用「2 * max_debate_rounds」是因为多头+空头各算一轮；
     风控用「3 * max_risk_discuss_rounds」因为有三派。
"""
from __future__ import annotations

from app.agents.utils.agent_states import AgentState


class ConditionalLogic:
    """Handles conditional logic for determining graph flow."""

    def __init__(self, max_debate_rounds=1, max_risk_discuss_rounds=1):
        """Initialize with configuration parameters."""
        self.max_debate_rounds = max_debate_rounds
        self.max_risk_discuss_rounds = max_risk_discuss_rounds

    def should_continue_market(self, state: AgentState):
        """Determine if market analysis should continue."""
        messages = state["messages"]
        last_message = messages[-1]
        if last_message.tool_calls:
            return "tools_market"
        return "Msg Clear Market"

    def should_continue_social(self, state: AgentState):
        """Determine if social media analysis should continue."""
        messages = state["messages"]
        last_message = messages[-1]
        if last_message.tool_calls:
            return "tools_social"
        return "Msg Clear Social"

    def should_continue_news(self, state: AgentState):
        """Determine if news analysis should continue."""
        messages = state["messages"]
        last_message = messages[-1]
        if last_message.tool_calls:
            return "tools_news"
        return "Msg Clear News"

    def should_continue_fundamentals(self, state: AgentState):
        """Determine if fundamentals analysis should continue."""
        messages = state["messages"]
        last_message = messages[-1]
        if last_message.tool_calls:
            return "tools_fundamentals"
        return "Msg Clear Fundamentals"

    def should_continue_debate(self, state: AgentState) -> str:
        """Determine if debate should continue.

        【多空辩论的调度逻辑】
          - count 是「已发言次数」，达到 2*轮数 就停止辩论、交给研究经理裁决
          - 否则看最后谁说的：Bull 刚说完 → 轮到 Bear；反之轮到 Bull
          这样 Bull/Bear 就自动来回交锋。
        """
        if (
            state["investment_debate_state"]["count"] >= 2 * self.max_debate_rounds
        ):  # 两位 agent 之间来回 max_debate_rounds 轮
            return "Research Manager"
        if state["investment_debate_state"]["current_response"].startswith("Bull"):
            return "Bear Researcher"
        return "Bull Researcher"

    def should_continue_risk_analysis(self, state: AgentState) -> str:
        """Determine if risk analysis should continue.

        【风控三派辩论的调度逻辑】
          与多空辩论同理，只是发言顺序是 激进→保守→中性→激进 的环形。
          通过 latest_speaker 字段记住「上次谁说的」，决定下一位发言者。
        """
        if (
            state["risk_debate_state"]["count"] >= 3 * self.max_risk_discuss_rounds
        ):  # 三位 agent 之间来回 max_risk_discuss_rounds 轮
            return "Portfolio Manager"
        if state["risk_debate_state"]["latest_speaker"].startswith("Aggressive"):
            return "Conservative Analyst"
        if state["risk_debate_state"]["latest_speaker"].startswith("Conservative"):
            return "Neutral Analyst"
        return "Aggressive Analyst"
