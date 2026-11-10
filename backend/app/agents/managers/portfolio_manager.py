# -*- coding: utf-8 -*-
"""基金经理 —— 整条流水线的「最终裁决者」。

【角色】风控三派辩论结束后，由它综合辩论 + 交易员计划 + 历史教训，
给出最终的五档评级：买 / 增持 / 持有 / 减持 / 卖（A股版词汇）。
这是整张图的终点，产出 final_trade_decision。

【为什么用深度模型】这是最高级别的决策节点，需要谨慎权衡风险与收益，
所以用 deep_thinking_llm。

【A股差异】评级词汇从参考项目的 Buy/Overweight/Hold/Underweight/Sell 改成
中文五档「买/增持/持有/减持/卖」，与 signal_processing 的解析和前端 §4.3 对齐。

【产出结构】Rating（评级）+ Executive Summary（执行摘要）+ Investment Thesis（投资逻辑），
并要求每个结论都必须锚定分析师辩论里的具体证据。
"""
from __future__ import annotations

from app.agents.utils.agent_utils import build_instrument_context, get_language_instruction


def create_portfolio_manager(llm, memory):
    def portfolio_manager_node(state) -> dict:

        instrument_context = build_instrument_context(state["company_of_interest"])

        history = state["risk_debate_state"]["history"]
        risk_debate_state = state["risk_debate_state"]
        market_research_report = state["market_report"]
        news_report = state["news_report"]
        fundamentals_report = state["fundamentals_report"]
        sentiment_report = state["sentiment_report"]
        trader_plan = state["investment_plan"]

        curr_situation = f"{market_research_report}\n\n{sentiment_report}\n\n{news_report}\n\n{fundamentals_report}"
        past_memories = memory.get_memories(curr_situation, n_matches=2)

        past_memory_str = ""
        for i, rec in enumerate(past_memories, 1):
            past_memory_str += rec["recommendation"] + "\n\n"

        prompt = f"""As the Portfolio Manager, synthesize the risk analysts' debate and deliver the final trading decision.

{instrument_context}

---

**Rating Scale** (use exactly one):
- **买 (Buy)**: Strong conviction to enter or add to position
- **增持 (Overweight)**: Favorable outlook, gradually increase exposure
- **持有 (Hold)**: Maintain current position, no action needed
- **减持 (Underweight)**: Reduce exposure, take partial profits
- **卖 (Sell)**: Exit position or avoid entry

**Context:**
- Trader's proposed plan: **{trader_plan}**
- Lessons from past decisions: **{past_memory_str}**

**Required Output Structure:**
1. **Rating**: State one of 买 / 增持 / 持有 / 减持 / 卖.
2. **Executive Summary**: A concise action plan covering entry strategy, position sizing, key risk levels, and time horizon.
3. **Investment Thesis**: Detailed reasoning anchored in the analysts' debate and past reflections.

---

**Risk Analysts Debate History:**
{history}

---

Be decisive and ground every conclusion in specific evidence from the analysts.{get_language_instruction()}"""

        response = llm.invoke(prompt)

        # 最终裁决写进 judge_decision（latest_speaker 标记为 Judge，表示辩论到此结束）
        new_risk_debate_state = {
            "judge_decision": response.content,
            "history": risk_debate_state["history"],
            "aggressive_history": risk_debate_state["aggressive_history"],
            "conservative_history": risk_debate_state["conservative_history"],
            "neutral_history": risk_debate_state["neutral_history"],
            "latest_speaker": "Judge",
            "current_aggressive_response": risk_debate_state["current_aggressive_response"],
            "current_conservative_response": risk_debate_state["current_conservative_response"],
            "current_neutral_response": risk_debate_state["current_neutral_response"],
            "count": risk_debate_state["count"],
        }

        return {
            "risk_debate_state": new_risk_debate_state,
            "final_trade_decision": response.content,  # 最终交易决策（整张图的产出）
        }

    return portfolio_manager_node
