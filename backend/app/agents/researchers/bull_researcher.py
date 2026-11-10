# -*- coding: utf-8 -*-
"""多头研究员 —— 辩论中的「看多方」。

【角色】只找「应该买入」的理由，并逐条反驳空头的质疑。

【「纯 Prompt 型」Agent】与分析师不同，它不调工具，只用 f-string 拼一段长
Prompt，把四份报告 + 辩论历史 + 空头上轮发言 + 历史经验喂给 LLM。
它产出的不是报告，而是一段「辩论发言」。

【状态更新要点】辩论节点只改 investment_debate_state 里的字段：
- history：追加本轮发言（给后续所有人看）
- bull_history：只追加多头自己的发言（供复盘/展示用）
- current_response：记下「本轮谁说了什么」（供条件边判断下一轮谁发言）
- count：发言计数 +1（供条件边判断是否该结束辩论）
"""
from __future__ import annotations


def create_bull_researcher(llm, memory):
    def bull_node(state) -> dict:
        investment_debate_state = state["investment_debate_state"]
        history = investment_debate_state.get("history", "")
        bull_history = investment_debate_state.get("bull_history", "")

        current_response = investment_debate_state.get("current_response", "")
        market_research_report = state["market_report"]
        sentiment_report = state["sentiment_report"]
        news_report = state["news_report"]
        fundamentals_report = state["fundamentals_report"]

        # 用四份报告拼成「当前情境」，作为记忆检索的 query（MVP 空记忆返回 []）
        curr_situation = f"{market_research_report}\n\n{sentiment_report}\n\n{news_report}\n\n{fundamentals_report}"
        past_memories = memory.get_memories(curr_situation, n_matches=2)

        past_memory_str = ""
        for i, rec in enumerate(past_memories, 1):
            past_memory_str += rec["recommendation"] + "\n\n"

        prompt = f"""You are a Bull Analyst advocating for investing in the stock. Your task is to build a strong, evidence-based case emphasizing growth potential, competitive advantages, and positive market indicators. Leverage the provided research and data to address concerns and counter bearish arguments effectively.

Key points to focus on:
- Growth Potential: Highlight the company's market opportunities, revenue projections, and scalability.
- Competitive Advantages: Emphasize factors like unique products, strong branding, or dominant market positioning.
- Positive Indicators: Use financial health, industry trends, and recent positive news as evidence.
- Bear Counterpoints: Critically analyze the bear argument with specific data and sound reasoning, addressing concerns thoroughly and showing why the bull perspective holds stronger merit.
- Engagement: Present your argument in a conversational style, engaging directly with the bear analyst's points and debating effectively rather than just listing data.

Resources available:
Market research report: {market_research_report}
Social media sentiment report: {sentiment_report}
Latest world affairs news: {news_report}
Company fundamentals report: {fundamentals_report}
Conversation history of the debate: {history}
Last bear argument: {current_response}
Reflections from similar situations and lessons learned: {past_memory_str}
Use this information to deliver a compelling bull argument, refute the bear's concerns, and engage in a dynamic debate that demonstrates the strengths of the bull position. You must also address reflections and learn from lessons and mistakes you made in the past.
"""

        response = llm.invoke(prompt)

        # 发言加「角色前缀」，方便后续条件边用 startswith 判断「谁刚说完」
        argument = f"Bull Analyst: {response.content}"

        new_investment_debate_state = {
            "history": history + "\n" + argument,           # 完整辩论史（供所有人看）
            "bull_history": bull_history + "\n" + argument,  # 仅多头的发言记录
            "bear_history": investment_debate_state.get("bear_history", ""),
            "current_response": argument,                   # 本轮发言（供判断下一轮）
            "count": investment_debate_state["count"] + 1,  # 发言计数 +1
        }

        return {"investment_debate_state": new_investment_debate_state}

    return bull_node
