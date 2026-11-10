# -*- coding: utf-8 -*-
"""用 LangGraph 的 StateGraph 把 12 个 Agent 拼成一张流水线图。

【这是理解整个框架最值得精读的文件】
  LangGraph 的核心思想：把每个 Agent 当成图里的一个「节点(node)」，
  用「边(edge)」定义它们之间的执行顺序，用「条件边(conditional edge)」
  在运行时决定「下一步去哪」。整个交易分析就是一个有向状态图。

【整张图的执行顺序】
  START
    └─ 4 个分析师（按 selected_analysts 顺序串行，每个都带工具循环）
           │   每个分析师：Agent ⇄ 工具节点（LLM 要调工具→去工具→回 Agent→…→写完报告→清消息→下一个）
    └─ Bull Researcher ⇄ Bear Researcher（多空辩论，轮数由 max_debate_rounds 控制）
    └─ Research Manager（研究经理，裁决 Buy/Sell/Hold → 产出 investment_plan）
    └─ Trader（交易员，产出 trader_investment_plan）
    └─ Aggressive ⇄ Conservative ⇄ Neutral（风控三派辩论）
    └─ Portfolio Manager（基金经理，产出 final_trade_decision 五档评级）
  END

【关键概念】
  - StateGraph(AgentState)：图共享一个状态，每个节点的返回值会 merge 回状态
  - add_node：注册节点
  - add_edge：固定顺序的边（无条件，必然跳转）
  - add_conditional_edges：条件边（运行时调用一个判断函数决定跳转目标）
  - ToolNode：LangGraph 提供的「执行工具」专用节点
  - "Msg Clear" 节点：清空消息列表（否则消息会无限累积、浪费 token）
"""
from __future__ import annotations

from typing import Any, Dict

from langgraph.graph import END, StateGraph, START

from app.agents.utils.agent_states import AgentState
from app.agents.utils.agent_utils import create_msg_delete
from app.agents.analysts import (
    create_market_analyst,
    create_fundamentals_analyst,
    create_news_analyst,
    create_social_media_analyst,
)
from app.agents.researchers import create_bull_researcher, create_bear_researcher
from app.agents.managers import create_research_manager, create_portfolio_manager
from app.agents.trader import create_trader
from app.agents.risk_mgmt import (
    create_aggressive_debator,
    create_neutral_debator,
    create_conservative_debator,
)

from .conditional_logic import ConditionalLogic


class GraphSetup:
    """Handles the setup and configuration of the agent graph."""

    def __init__(
        self,
        quick_thinking_llm: Any,
        deep_thinking_llm: Any,
        tool_nodes: Dict[str, Any],
        bull_memory,
        bear_memory,
        trader_memory,
        invest_judge_memory,
        portfolio_manager_memory,
        conditional_logic: ConditionalLogic,
    ):
        """Initialize with required components."""
        self.quick_thinking_llm = quick_thinking_llm
        self.deep_thinking_llm = deep_thinking_llm
        self.tool_nodes = tool_nodes
        self.bull_memory = bull_memory
        self.bear_memory = bear_memory
        self.trader_memory = trader_memory
        self.invest_judge_memory = invest_judge_memory
        self.portfolio_manager_memory = portfolio_manager_memory
        self.conditional_logic = conditional_logic

    def setup_graph(
        self, selected_analysts=["market", "social", "news", "fundamentals"]
    ):
        """Set up and compile the agent workflow graph.

        Args:
            selected_analysts (list): List of analyst types to include. Options are:
                - "market": Market analyst
                - "social": Social media analyst
                - "news": News analyst
                - "fundamentals": Fundamentals analyst
        """
        if len(selected_analysts) == 0:
            raise ValueError("Trading Agents Graph Setup Error: no analysts selected!")

        # 【分析师节点】每个被选中的分析师会生成三样东西：
        #   analyst_nodes[type] —— Agent 本体（一个节点函数）
        #   delete_nodes[type]  —— 「清空消息」节点（防止消息无限累积）
        #   tool_nodes[type]    —— 该分析师可用的工具节点（ToolNode）
        analyst_nodes = {}
        delete_nodes = {}
        tool_nodes = {}

        if "market" in selected_analysts:
            analyst_nodes["market"] = create_market_analyst(self.quick_thinking_llm)
            delete_nodes["market"] = create_msg_delete()
            tool_nodes["market"] = self.tool_nodes["market"]

        if "social" in selected_analysts:
            analyst_nodes["social"] = create_social_media_analyst(self.quick_thinking_llm)
            delete_nodes["social"] = create_msg_delete()
            tool_nodes["social"] = self.tool_nodes["social"]

        if "news" in selected_analysts:
            analyst_nodes["news"] = create_news_analyst(self.quick_thinking_llm)
            delete_nodes["news"] = create_msg_delete()
            tool_nodes["news"] = self.tool_nodes["news"]

        if "fundamentals" in selected_analysts:
            analyst_nodes["fundamentals"] = create_fundamentals_analyst(self.quick_thinking_llm)
            delete_nodes["fundamentals"] = create_msg_delete()
            tool_nodes["fundamentals"] = self.tool_nodes["fundamentals"]

        # 【研究员与经理节点】注意两类 Agent 的构造差异：
        #   - 研究员/交易员需要「记忆」参数（读历史经验教训）
        #   - 研究经理用 deep_thinking_llm（深度模型做裁决），其余大多用 quick
        bull_researcher_node = create_bull_researcher(self.quick_thinking_llm, self.bull_memory)
        bear_researcher_node = create_bear_researcher(self.quick_thinking_llm, self.bear_memory)
        research_manager_node = create_research_manager(self.deep_thinking_llm, self.invest_judge_memory)
        trader_node = create_trader(self.quick_thinking_llm, self.trader_memory)

        # Create risk analysis nodes
        aggressive_analyst = create_aggressive_debator(self.quick_thinking_llm)
        neutral_analyst = create_neutral_debator(self.quick_thinking_llm)
        conservative_analyst = create_conservative_debator(self.quick_thinking_llm)
        portfolio_manager_node = create_portfolio_manager(
            self.deep_thinking_llm, self.portfolio_manager_memory
        )

        # 【建图】StateGraph 是 LangGraph 的核心：以 AgentState 为共享状态构建有向图
        workflow = StateGraph(AgentState)

        # 把分析师相关的三个节点都注册进图：Agent 本体 / 消息清理 / 工具节点
        for analyst_type, node in analyst_nodes.items():
            workflow.add_node(f"{analyst_type.capitalize()} Analyst", node)
            workflow.add_node(
                f"Msg Clear {analyst_type.capitalize()}", delete_nodes[analyst_type]
            )
            workflow.add_node(f"tools_{analyst_type}", tool_nodes[analyst_type])

        # Add other nodes
        workflow.add_node("Bull Researcher", bull_researcher_node)
        workflow.add_node("Bear Researcher", bear_researcher_node)
        workflow.add_node("Research Manager", research_manager_node)
        workflow.add_node("Trader", trader_node)
        workflow.add_node("Aggressive Analyst", aggressive_analyst)
        workflow.add_node("Neutral Analyst", neutral_analyst)
        workflow.add_node("Conservative Analyst", conservative_analyst)
        workflow.add_node("Portfolio Manager", portfolio_manager_node)

        # ============ 定义边（图的执行流向）============
        # 起点 → 第一个分析师
        first_analyst = selected_analysts[0]
        workflow.add_edge(START, f"{first_analyst.capitalize()} Analyst")

        # 【分析师串行连接 + 工具循环】
        for i, analyst_type in enumerate(selected_analysts):
            current_analyst = f"{analyst_type.capitalize()} Analyst"
            current_tools = f"tools_{analyst_type}"
            current_clear = f"Msg Clear {analyst_type.capitalize()}"

            # 关键机制：条件边实现「Agent ⇄ 工具」循环。
            # 判断函数 should_continue_* 检查最后一条消息是否含 tool_calls：
            #   有 tool_calls → 去工具节点（执行工具，结果塞回消息）
            #   无 tool_calls → 去消息清理节点（说明报告写完了）
            workflow.add_conditional_edges(
                current_analyst,
                getattr(self.conditional_logic, f"should_continue_{analyst_type}"),
                [current_tools, current_clear],
            )
            # 工具执行完 → 回到 Agent（让 LLM 看到工具结果后继续分析/写报告）
            workflow.add_edge(current_tools, current_analyst)

            # 报告写完、消息清空后 → 去下一个分析师；最后一个则进入多空辩论
            if i < len(selected_analysts) - 1:
                next_analyst = f"{selected_analysts[i+1].capitalize()} Analyst"
                workflow.add_edge(current_clear, next_analyst)
            else:
                workflow.add_edge(current_clear, "Bull Researcher")

        # ============ 多空辩论的条件循环 ============
        # Bull 说完 → 判断：辩够了去 Research Manager，否则轮 Bear；反之亦然。
        # 这是一个「来回踢皮球」的环，直到辩论轮数达到上限才跳出。
        workflow.add_conditional_edges(
            "Bull Researcher",
            self.conditional_logic.should_continue_debate,
            {
                "Bear Researcher": "Bear Researcher",
                "Research Manager": "Research Manager",
            },
        )
        workflow.add_conditional_edges(
            "Bear Researcher",
            self.conditional_logic.should_continue_debate,
            {
                "Bull Researcher": "Bull Researcher",
                "Research Manager": "Research Manager",
            },
        )
        # 研究经理裁决后 → 交给交易员制定具体交易计划
        workflow.add_edge("Research Manager", "Trader")
        # 交易员 → 风控辩论的第一位发言者（激进派）
        workflow.add_edge("Trader", "Aggressive Analyst")

        # ============ 风控三派辩论的条件循环 ============
        # 激进 → 保守 → 中性 → 激进 ... 环形循环，轮数够了就交给基金经理。
        workflow.add_conditional_edges(
            "Aggressive Analyst",
            self.conditional_logic.should_continue_risk_analysis,
            {
                "Conservative Analyst": "Conservative Analyst",
                "Portfolio Manager": "Portfolio Manager",
            },
        )
        workflow.add_conditional_edges(
            "Conservative Analyst",
            self.conditional_logic.should_continue_risk_analysis,
            {
                "Neutral Analyst": "Neutral Analyst",
                "Portfolio Manager": "Portfolio Manager",
            },
        )
        workflow.add_conditional_edges(
            "Neutral Analyst",
            self.conditional_logic.should_continue_risk_analysis,
            {
                "Aggressive Analyst": "Aggressive Analyst",
                "Portfolio Manager": "Portfolio Manager",
            },
        )

        # 基金经理是终点
        workflow.add_edge("Portfolio Manager", END)

        # 编译图（校验结构、生成可执行对象）并返回
        return workflow.compile()
