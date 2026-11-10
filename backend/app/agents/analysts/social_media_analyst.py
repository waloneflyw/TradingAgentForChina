# -*- coding: utf-8 -*-
"""社媒/情绪分析师 —— 工具型 Agent。

【角色】分析社交媒体讨论、公司新闻、公众情绪，产出 sentiment_report。
关注「人们在说什么、每天情绪如何变化」，为交易提供情绪面依据。

【A股差异】参考项目只绑 get_news 一个工具；本版额外绑 get_fundamentals，
读「千股千评/人气榜」快照里的综合得分、关注指数等散户情绪字段
（A股没有成熟的 Twitter/Reddit 情绪源，用个股关注度 + 新闻做降级替代）。
"""
from __future__ import annotations

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from app.agents.utils.agent_utils import (
    build_instrument_context,
    get_fundamentals,
    get_language_instruction,
    get_news,
)


def create_social_media_analyst(llm):
    def social_media_analyst_node(state):
        current_date = state["trade_date"]
        instrument_context = build_instrument_context(state["company_of_interest"])

        tools = [
            get_news,
            get_fundamentals,
        ]

        system_message = (
            "You are a social media and company specific news researcher/analyst tasked with analyzing social media posts, recent company news, and public sentiment for a specific company over the past week. You will be given a company's name; your objective is to write a comprehensive long report detailing your analysis, insights, and implications for traders and investors on this company's current state after looking at social media and what people are saying about that company, analyzing sentiment data of what people feel each day about the company, and looking at recent company news. Use the get_news(ticker, start_date, end_date) tool to search for company-specific news and social media discussions. Use get_fundamentals(ticker, curr_date) to read retail-attention snapshots (popularity rank, attention index, composite score). Try to look at all sources possible from social media to sentiment to news. Provide specific, actionable insights with supporting evidence to help traders make informed decisions."
            + """ Make sure to append a Markdown table at the end of the report to organize key points in the report, organized and easy to read."""
            + " This is the A-share (China) market: retail sentiment is a dominant driver; note attention/hot-rank signals, limit-up board participation, and how hype can detach prices from fundamentals."
            + get_language_instruction()
        )

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are a helpful AI assistant, collaborating with other assistants."
                    " Use the provided tools to progress towards answering the question."
                    " If you are unable to fully answer, that's OK; another assistant with different tools"
                    " will help where you left off. Execute what you can to make progress."
                    " If you or any other assistant has the FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL** or deliverable,"
                    " prefix your response with FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL** so the team knows to stop."
                    " You have access to the following tools: {tool_names}.\n{system_message}"
                    "For your reference, the current date is {current_date}. {instrument_context}",
                ),
                MessagesPlaceholder(variable_name="messages"),
            ]
        )

        prompt = prompt.partial(system_message=system_message)
        prompt = prompt.partial(tool_names=", ".join([tool.name for tool in tools]))
        prompt = prompt.partial(current_date=current_date)
        prompt = prompt.partial(instrument_context=instrument_context)

        chain = prompt | llm.bind_tools(tools)

        result = chain.invoke(state["messages"])

        report = ""

        if len(result.tool_calls) == 0:
            report = result.content

        return {
            "messages": [result],
            "sentiment_report": report,
        }

    return social_media_analyst_node
