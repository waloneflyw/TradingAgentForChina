# -*- coding: utf-8 -*-
"""基本面分析师 —— 「工具型」Agent 的代表。

【角色】分析公司财报与估值（公司概况、三大财务报表），产出一份基本面报告，
写入状态字段 fundamentals_report。

【「工具型 Agent」的标准结构】（4 个分析师都长这样）
  1. create_xxx_analyst(llm) 是「闭包工厂」：传入 LLM，返回节点函数。
  2. 节点函数里用 ChatPromptTemplate.from_messages 拼 system 提示，
     并把该分析师能用的工具通过 llm.bind_tools(tools) 暴露给 LLM。
  3. chain.invoke(state["messages"]) 触发一次 LLM 调用。
  4. 关键判断：如果这次 LLM 返回了 tool_calls（它想调工具拉数据），
     说明报告还没写完，把消息返回去、让图把它导向工具节点；
     如果 tool_calls 为空，说明它写完了，报告内容写进状态。

【工具循环是怎么跑起来的】
  分析师节点 →(LLM 想调工具)→ 工具节点 →(执行完、结果塞回消息)→ 分析师节点
  → … 反复直到 LLM 不再调工具、写出完整报告 → 清消息 → 下一个分析师。
  这个循环由 graph/setup.py 的条件边 + conditional_logic.should_continue_* 实现。

【A股差异】参考项目用 4 个工具（get_fundamentals + 三张报表分开），
本版把三张报表合并成一个 get_financial_statements（statement_type=balance/income/cashflow）。
"""
from __future__ import annotations

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from app.agents.utils.agent_utils import (
    build_instrument_context,
    get_financial_statements,
    get_fundamentals,
    get_language_instruction,
)


def create_fundamentals_analyst(llm):
    def fundamentals_analyst_node(state):
        # 从共享状态里取需要的字段
        current_date = state["trade_date"]
        instrument_context = build_instrument_context(state["company_of_interest"])

        # 基本面相关的 2 个工具（三张报表合并进 get_financial_statements）
        tools = [
            get_fundamentals,
            get_financial_statements,
        ]

        system_message = (
            "You are a researcher tasked with analyzing fundamental information over the past week about a company. Please write a comprehensive report of the company's fundamental information such as financial documents, company profile, basic company financials, and company financial history to gain a full view of the company's fundamental information to inform traders. Make sure to include as much detail as possible. Provide specific, actionable insights with supporting evidence to help traders make informed decisions."
            + " Make sure to append a Markdown table at the end of the report to organize key points in the report, organized and easy to read."
            + " Use the available tools: `get_fundamentals` for a comprehensive company overview (industry, valuation, profitability, growth, and current price/attention), and `get_financial_statements` for the three financial statements — pass `statement_type` as `balance`, `income`, or `cashflow` (or `all` to get all three at once)."
            + " This is the A-share (China) market: pay attention to earnings-report seasons, ST/*ST delisting-risk labels, shareholder/insider changes, and the regulatory environment; note any risk of financial fraud or goodwill impairment."
            + get_language_instruction(),
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
                # 消息占位符：运行时把历史消息列表（state["messages"]）插到这里
                MessagesPlaceholder(variable_name="messages"),
            ]
        )

        # .partial() 预填充那些「每个节点都固定」的变量，剩下 messages 在 invoke 时传
        prompt = prompt.partial(system_message=system_message)
        prompt = prompt.partial(tool_names=", ".join([tool.name for tool in tools]))
        prompt = prompt.partial(current_date=current_date)
        prompt = prompt.partial(instrument_context=instrument_context)

        # 【关键】用 | 运算符把 prompt 和「绑定了工具的 LLM」串成一条链
        chain = prompt | llm.bind_tools(tools)

        result = chain.invoke(state["messages"])

        report = ""

        # 【工具循环的关键判断】LLM 这一轮如果还在请求调工具，说明它还没写完报告；
        # 只有 tool_calls 为空时，才把它的输出当作最终报告写进状态。
        if len(result.tool_calls) == 0:
            report = result.content

        return {
            "messages": [result],
            "fundamentals_report": report,
        }

    return fundamentals_analyst_node
