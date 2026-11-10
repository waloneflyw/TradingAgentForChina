# -*- coding: utf-8 -*-
"""交易员 —— 把投资计划转成具体交易决策。

【角色】拿到研究经理的投资计划（investment_plan）后，结合四份报告和历史经验，
产出具体的交易计划 trader_investment_plan，结尾必带
"FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL**" 明确表态。

【纯 Prompt 型】不调工具，用 messages 列表（system + user）组织 Prompt。

【一个细节】用 functools.partial 把节点函数固定 name="Trader"，
这样它既能当图节点用，又能通过 state 返回 sender 字段标明身份。
"""
from __future__ import annotations

import functools

from app.agents.utils.agent_utils import build_instrument_context


def create_trader(llm, memory):
    def trader_node(state, name):
        company_name = state["company_of_interest"]
        instrument_context = build_instrument_context(company_name)
        investment_plan = state["investment_plan"]
        market_research_report = state["market_report"]
        sentiment_report = state["sentiment_report"]
        news_report = state["news_report"]
        fundamentals_report = state["fundamentals_report"]

        curr_situation = f"{market_research_report}\n\n{sentiment_report}\n\n{news_report}\n\n{fundamentals_report}"
        past_memories = memory.get_memories(curr_situation, n_matches=2)

        past_memory_str = ""
        if past_memories:
            for i, rec in enumerate(past_memories, 1):
                past_memory_str += rec["recommendation"] + "\n\n"
        else:
            past_memory_str = "No past memories found."

        context = {
            "role": "user",
            "content": f"Based on a comprehensive analysis by a team of analysts, here is an investment plan tailored for {company_name}. {instrument_context} This plan incorporates insights from current technical market trends, macroeconomic indicators, and social media sentiment. Use this plan as a foundation for evaluating your next trading decision.\n\nProposed Investment Plan: {investment_plan}\n\nLeverage these insights to make an informed and strategic decision.",
        }

        messages = [
            {
                "role": "system",
                "content": f"""You are a trading agent analyzing market data to make investment decisions. Based on your analysis, provide a specific recommendation to buy, sell, or hold. End with a firm decision and always conclude your response with 'FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL**' to confirm your recommendation. Apply lessons from past decisions to strengthen your analysis. Here are reflections from similar situations you traded in and the lessons learned: {past_memory_str}""",
            },
            context,
        ]

        result = llm.invoke(messages)

        return {
            "messages": [result],
            "trader_investment_plan": result.content,  # 交易员计划（供风控团队评审）
            "sender": name,
        }

    # 用 functools.partial 把 name 固定为 "Trader"，得到一个只收 state 的节点函数
    return functools.partial(trader_node, name="Trader")
