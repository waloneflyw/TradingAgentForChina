# -*- coding: utf-8 -*-
"""定义贯穿整张图（11-agent 流水线）的「共享状态」。

【作用】LangGraph 的所有节点共享同一个状态字典，每个节点读取它需要的字段、
返回它更新的字段（其余字段自动保留）。这里用 TypedDict 定义状态结构。

【三层状态】
- InvestDebateState —— 多空辩论（牛熊研究员）的私有子状态，嵌套在 AgentState 里
- RiskDebateState   —— 风控三派辩论的私有子状态，嵌套在 AgentState 里
- AgentState        —— 顶层总状态，继承 LangGraph 的 MessagesState（自带 messages 字段 + 合并逻辑）

【为什么「嵌套」】辩论是一段反复循环的子流程，它的中间产物（谁说过什么、说了几轮）
只对辩论自己有意义。包成一个 dict 字段，既能整体传入/传出辩论节点，又不污染顶层状态。

字段名与参考项目保持一致（conditional_logic / signal_processing 都依赖它们）。
"""
from __future__ import annotations

from typing import Annotated

from typing_extensions import TypedDict

from langgraph.graph import MessagesState


class InvestDebateState(TypedDict):
    """多空辩论子状态。"""
    bull_history: Annotated[str, "多头历史发言"]
    bear_history: Annotated[str, "空头历史发言"]
    history: Annotated[str, "完整辩论历史"]
    current_response: Annotated[str, "最近一次发言（带 Bull/Bear 前缀，路由靠它判断）"]
    judge_decision: Annotated[str, "研究经理裁决"]
    count: Annotated[int, "已发言次数（终止条件 count >= 2*max_debate_rounds）"]


class RiskDebateState(TypedDict):
    """风控三派辩论子状态。"""
    aggressive_history: Annotated[str, "激进派历史发言"]
    conservative_history: Annotated[str, "保守派历史发言"]
    neutral_history: Annotated[str, "中性派历史发言"]
    history: Annotated[str, "完整辩论历史"]
    latest_speaker: Annotated[str, "最近发言者（带 Aggressive/Conservative/Neutral 前缀，路由靠它轮转）"]
    current_aggressive_response: Annotated[str, "激进派最近发言"]
    current_conservative_response: Annotated[str, "保守派最近发言"]
    current_neutral_response: Annotated[str, "中性派最近发言"]
    judge_decision: Annotated[str, "组合经理裁决"]
    count: Annotated[int, "已发言次数（终止条件 count >= 3*max_risk_discuss_rounds）"]


class AgentState(MessagesState):
    """顶层总状态。字段按流水线阶段分组：

    - 输入：company_of_interest（股票代码，如 600519.SH）、trade_date（分析日期）
    - 分析师产出：market/sentiment/news/fundamentals 四份报告
    - 研究阶段：investment_debate_state（多空辩论）+ investment_plan（研究经理裁决）
    - 交易阶段：trader_investment_plan（交易员计划）
    - 风控阶段：risk_debate_state（三派辩论）+ final_trade_decision（组合经理最终结论）
    """
    company_of_interest: Annotated[str, "被分析的股票代码（带交易所后缀，如 600519.SH）"]
    trade_date: Annotated[str, "分析基准日期"]

    sender: Annotated[str, "发送消息的 agent 名"]

    # 分析师阶段产出
    market_report: Annotated[str, "市场/技术面分析师报告"]
    sentiment_report: Annotated[str, "社会情绪分析师报告"]
    news_report: Annotated[str, "新闻/宏观分析师报告"]
    fundamentals_report: Annotated[str, "基本面分析师报告"]

    # 研究团队辩论阶段
    investment_debate_state: Annotated[InvestDebateState, "多空辩论当前状态"]
    investment_plan: Annotated[str, "研究经理汇总的投资计划"]

    trader_investment_plan: Annotated[str, "交易员生成的交易计划"]

    # 风控团队辩论阶段
    risk_debate_state: Annotated[RiskDebateState, "风控三派辩论当前状态"]
    final_trade_decision: Annotated[str, "组合经理最终决策（signal_processing 据此抽评级）"]
