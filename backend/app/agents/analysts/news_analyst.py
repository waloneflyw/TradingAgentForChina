# -*- coding: utf-8 -*-
"""新闻/宏观分析师 —— 工具型 Agent。

【角色】分析公司新闻 + 公告 + 股东增减持 + 大盘宏观，产出 news_report。
聚焦影响交易与宏观经济的新闻趋势，为交易员提供「当前在发生什么」。

【A股差异】参考项目用 get_news + get_global_news 两个工具；本版拆成四个更贴合
A股数据源的工具：
- get_news              个股新闻
- get_announcements     公司公告（财报/停复牌/重组等）
- get_shareholder_changes 股东/高管增减持 + 龙虎榜（对应美股 insider transactions）
- get_market_overview   大盘概览（核心指数/板块涨跌/北向资金，对应 global news）

【结构】「工具型 Agent」模式，详见 fundamentals_analyst.py 顶部注释。
"""
from __future__ import annotations

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from app.agents.utils.agent_utils import (
    build_instrument_context,
    get_announcements,
    get_language_instruction,
    get_market_overview,
    get_news,
    get_shareholder_changes,
)


def create_news_analyst(llm):
    def news_analyst_node(state):
        current_date = state["trade_date"]
        instrument_context = build_instrument_context(state["company_of_interest"])

        tools = [
            get_news,
            get_announcements,
            get_shareholder_changes,
            get_market_overview,
        ]

        system_message = (
            "You are a news researcher tasked with analyzing recent news and trends over the past week. Please write a comprehensive report of the current state of the world that is relevant for trading and macroeconomics. Use the available tools: get_news(ticker, start_date, end_date) for company-specific news, get_announcements(ticker, start_date, end_date) for official company announcements (earnings, suspensions, restructuring), get_shareholder_changes(ticker) for insider/blockholder buying or selling and dragon-tiger-list activity, and get_market_overview(curr_date) for the broad market (major indices, sector performance, northbound capital flows). Provide specific, actionable insights with supporting evidence to help traders make informed decisions."
            + """ Make sure to append a Markdown table at the end of the report to organize key points in the report, organized and easy to read."""
            + " This is the A-share (China) market: weigh policy/regulatory news, industry catalysts, and northbound capital flows heavily; treat announcements about capital restructuring, asset injections, and ST-removal as major price drivers."
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
            "news_report": report,
        }

    return news_analyst_node
