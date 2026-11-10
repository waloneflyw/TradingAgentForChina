# -*- coding: utf-8 -*-
"""整个多智能体交易框架的「总控类」。

【它在架构里的位置】
  这是对外的唯一入口。用户只需创建 TradingAgentsGraph 并调用 .propagate()
  即可跑完整套分析流水线。它本身不实现任何「智能」，只负责「组装」：

    1. 读取配置        —— self.config（来自 Config.llm_config()）
    2. 创建两个 LLM    —— deep_thinking_llm（深度推理）/ quick_thinking_llm（快速）
    3. 创建 5 个记忆库 —— FinancialSituationMemory（多/空/交易员/研究经理/基金经理）
    4. 创建工具节点    —— 按分析师分组的 LangGraph ToolNode
    5. 组装子模块      —— ConditionalLogic / GraphSetup / Propagator / SignalProcessor
    6. 编译状态图      —— graph_setup.setup_graph() 返回编译好的 LangGraph 图

【「双模型分级」的设计思路】
  贵而强的模型（deep）只用在「关键裁决」上（研究经理、基金经理）；
  便宜而快的模型（quick）用在「量大但相对简单」的角色上（分析师、辩论、交易员）。
  这是多智能体系统里典型的成本-质量平衡策略。

【一次分析的完整生命周期】
  propagate()  → 构造初始状态 → graph.invoke() 跑图
  → process_signal() → 把基金经理的长文本提炼成单个评级词（买/增持/持有/减持/卖）

【A股 MVP 差异】
  - 移除 Reflector（复盘写经验留到 L3），记忆库只用空实例。
  - 工具绑定换成 A股 9 工具（见 _create_tool_nodes）。
  - 日志写进 backend/logs/ 而非参考项目的 eval_results/。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from langgraph.prebuilt import ToolNode

from app.config import BACKEND_DIR, Config
from app.llm_clients import create_llm_client
from app.agents.utils.memory import FinancialSituationMemory
from app.agents.utils.agent_utils import (
    get_stock_data,
    get_indicators,
    get_fundamentals,
    get_financial_statements,
    get_news,
    get_announcements,
    get_shareholder_changes,
    get_market_overview,
)

from .conditional_logic import ConditionalLogic
from .setup import GraphSetup
from .propagation import Propagator
from .signal_processing import SignalProcessor


class TradingAgentsGraph:
    """Main class that orchestrates the trading agents framework."""

    def __init__(
        self,
        selected_analysts=["market", "social", "news", "fundamentals"],
        debug=False,
        config: Optional[Dict[str, Any]] = None,
        callbacks: Optional[List] = None,
    ):
        """Initialize the trading agents graph and components.

        Args:
            selected_analysts: List of analyst types to include
            debug: Whether to run in debug mode (stream + pretty_print)
            config: Configuration dictionary. If None, uses Config.llm_config()
            callbacks: Optional list of callback handlers (e.g., for tracking LLM/tool stats)
        """
        self.debug = debug
        self.config = config or Config.llm_config()
        self.callbacks = callbacks or []

        # 根据厂商（openai/deepseek 等）准备各自的「思考强度」参数
        llm_kwargs = self._get_provider_kwargs()

        # 若有回调处理器（如 CLI 里统计 token/工具调用次数），一并传给 LLM 构造器
        if self.callbacks:
            llm_kwargs["callbacks"] = self.callbacks

        # 【双模型分级】创建两个 LLM：
        #   deep_thinking_llm  → 深度思考模型，用于研究经理、基金经理的关键裁决
        #   quick_thinking_llm → 快速模型，用于分析师、辩论、交易员等高频角色
        deep_client = create_llm_client(
            provider=self.config["llm_provider"],
            model=self.config["deep_think_llm"],
            base_url=self.config.get("backend_url"),
            **llm_kwargs,
        )
        quick_client = create_llm_client(
            provider=self.config["llm_provider"],
            model=self.config["quick_think_llm"],
            base_url=self.config.get("backend_url"),
            **llm_kwargs,
        )

        self.deep_thinking_llm = deep_client.get_llm()
        self.quick_thinking_llm = quick_client.get_llm()

        # 【记忆库】每个需要「从错误中学习」的角色各持有一个独立记忆实例。
        # 它们共享同一种检索算法（BM25），但各自存自己的「情境→经验教训」对，
        # 这样多头和空头不会互相污染记忆。MVP 阶段都是空实例。
        self.bull_memory = FinancialSituationMemory("bull_memory", self.config)
        self.bear_memory = FinancialSituationMemory("bear_memory", self.config)
        self.trader_memory = FinancialSituationMemory("trader_memory", self.config)
        self.invest_judge_memory = FinancialSituationMemory("invest_judge_memory", self.config)
        self.portfolio_manager_memory = FinancialSituationMemory("portfolio_manager_memory", self.config)

        # 工具节点：把「分析师可调用的工具函数」按分析师类型分组，包装成 LangGraph 的 ToolNode
        self.tool_nodes = self._create_tool_nodes()

        # 【组装子模块】各自职责单一：
        #   ConditionalLogic —— 图里「接下来该走哪条边」的判断逻辑
        #   GraphSetup       —— 真正把节点/边拼成一张 StateGraph 并编译
        #   Propagator       —— 构造初始状态
        #   SignalProcessor  —— 从长文本提取最终评级词
        self.conditional_logic = ConditionalLogic(
            max_debate_rounds=self.config["max_debate_rounds"],
            max_risk_discuss_rounds=self.config["max_risk_discuss_rounds"],
        )
        self.graph_setup = GraphSetup(
            self.quick_thinking_llm,
            self.deep_thinking_llm,
            self.tool_nodes,
            self.bull_memory,
            self.bear_memory,
            self.trader_memory,
            self.invest_judge_memory,
            self.portfolio_manager_memory,
            self.conditional_logic,
        )

        self.propagator = Propagator()
        self.signal_processor = SignalProcessor(self.quick_thinking_llm)

        # 状态追踪：curr_state 保存最近一次运行结果，
        # log_states_dict 按「日期→完整状态」记录日志
        self.curr_state = None
        self.ticker = None
        self.log_states_dict = {}  # date to full state dict

        # 【关键一步】编译整张状态图。setup_graph 会返回一个可 invoke/stream 的 LangGraph 图
        self.graph = self.graph_setup.setup_graph(selected_analysts)

    def _get_provider_kwargs(self) -> Dict[str, Any]:
        """Get provider-specific kwargs for LLM client creation."""
        kwargs = {}
        provider = self.config.get("llm_provider", "").lower()

        if provider == "openai":
            reasoning_effort = self.config.get("openai_reasoning_effort")
            if reasoning_effort:
                kwargs["reasoning_effort"] = reasoning_effort

        elif provider == "deepseek":
            # DeepSeek V4 thinking is on by default; pass the toggle to the
            # client so it can disable thinking (avoids reasoning_content 400).
            kwargs["deepseek_thinking"] = self.config.get("deepseek_thinking", False)

        return kwargs

    def _create_tool_nodes(self) -> Dict[str, Any]:
        """Create tool nodes for different data sources.

        【设计要点】每个分析师只拿到「它该用的」工具子集（A股 9 工具绑定）：
          - market      → 股价数据(get_stock_data) + 技术指标(get_indicators)
          - social      → 新闻(get_news) + 基本面快照(get_fundamentals，读千股千评/人气)
          - news        → 个股新闻 + 公告 + 股东增减持 + 大盘概览
          - fundamentals→ 公司概况(get_fundamentals) + 三大报表(get_financial_statements)
        工具函数本身是 @tool 装饰的薄壳（见 app/tools/stock_tools.py），
        它们只做一件事：把参数转发给数据层 route()。
        """
        return {
            "market": ToolNode(
                [
                    get_stock_data,
                    get_indicators,
                ]
            ),
            "social": ToolNode(
                [
                    get_news,
                    get_fundamentals,
                ]
            ),
            "news": ToolNode(
                [
                    get_news,
                    get_announcements,
                    get_shareholder_changes,
                    get_market_overview,
                ]
            ),
            "fundamentals": ToolNode(
                [
                    get_fundamentals,
                    get_financial_statements,
                ]
            ),
        }

    def propagate(self, company_name, trade_date) -> Tuple[Dict[str, Any], str]:
        """Run the trading agents graph for a company on a specific date.

        【主入口】这是「正推」一次分析的核心方法：
          1. 用 Propagator 构造初始状态（所有报告为空、辩论计数清零）
          2. 调用 graph.invoke() 让 LangGraph 沿着编排好的流水线跑完
          3. 保存最终状态，并用 SignalProcessor 把结论提炼成单个评级词

        Returns:
            (final_state, rating) —— 最终状态字典 + 五档评级词
        """

        self.ticker = company_name

        # 构造初始状态：把「股票代码 + 日期」装进一个 AgentState 字典
        init_agent_state = self.propagator.create_initial_state(company_name, trade_date)
        # 图运行参数（recursion_limit 等，因为辩论会循环经过同一批节点）
        args = self.propagator.get_graph_args()

        if self.debug:
            # Debug mode with tracing
            trace = []
            for chunk in self.graph.stream(init_agent_state, **args):
                if len(chunk["messages"]) == 0:
                    pass
                else:
                    chunk["messages"][-1].pretty_print()
                    trace.append(chunk)

            final_state = trace[-1]
        else:
            # Standard mode without tracing
            final_state = self.graph.invoke(init_agent_state, **args)

        # Store current state
        self.curr_state = final_state

        # Log state
        self._log_state(trade_date, final_state)

        # Return decision and processed signal
        return final_state, self.process_signal(final_state["final_trade_decision"])

    def _log_state(self, trade_date, final_state):
        """Log the final state to a JSON file under backend/logs/."""
        self.log_states_dict[str(trade_date)] = {
            "company_of_interest": final_state["company_of_interest"],
            "trade_date": final_state["trade_date"],
            "market_report": final_state["market_report"],
            "sentiment_report": final_state["sentiment_report"],
            "news_report": final_state["news_report"],
            "fundamentals_report": final_state["fundamentals_report"],
            "investment_debate_state": {
                "bull_history": final_state["investment_debate_state"]["bull_history"],
                "bear_history": final_state["investment_debate_state"]["bear_history"],
                "history": final_state["investment_debate_state"]["history"],
                "current_response": final_state["investment_debate_state"]["current_response"],
                "judge_decision": final_state["investment_debate_state"]["judge_decision"],
            },
            "trader_investment_decision": final_state["trader_investment_plan"],
            "risk_debate_state": {
                "aggressive_history": final_state["risk_debate_state"]["aggressive_history"],
                "conservative_history": final_state["risk_debate_state"]["conservative_history"],
                "neutral_history": final_state["risk_debate_state"]["neutral_history"],
                "history": final_state["risk_debate_state"]["history"],
                "judge_decision": final_state["risk_debate_state"]["judge_decision"],
            },
            "investment_plan": final_state["investment_plan"],
            "final_trade_decision": final_state["final_trade_decision"],
        }

        # Save to file（报告落库是阶段 4 的事，这里先落 JSON 日志便于验收）
        directory = BACKEND_DIR / "logs" / self.ticker / "TradingAgentsStrategy_logs"
        directory.mkdir(parents=True, exist_ok=True)

        with open(
            directory / f"full_states_log_{trade_date}.json",
            "w",
            encoding="utf-8",
        ) as f:
            json.dump(self.log_states_dict, f, indent=4, ensure_ascii=False)

    def process_signal(self, full_signal):
        """Process a signal to extract the core decision."""
        return self.signal_processor.process_signal(full_signal)
