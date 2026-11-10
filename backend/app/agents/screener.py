# -*- coding: utf-8 -*-
"""选股 agent —— 量化初筛（轻量工具型 agent）。

【角色】把用户「自然语言标签」（如"新能源、PE<30、ROE>10"）翻译成
get_stock_screener 的筛选参数并调用，再把返回的候选池总结成可读列表。

【为什么不用 11-agent 那么重】选股是「广撒网」：一次从全市场挑出几十只候选，
不需要逐只深研（那是单股分析 agent 的事）。所以这里只绑一个 SQL 初筛工具，
用一个「手动工具循环」跑完：LLM 想调工具 → 执行 → 看结果 → 总结。

【手动工具循环 vs LangGraph】
  单股分析用 LangGraph 是因为有 12 个节点 + 复杂条件边。选股只有「一个 agent
  反复调一个工具」的简单循环，手动 while 循环更直观、更好理解、更少依赖。

【MVP 边界】本阶段只做「量化初筛列表」，LLM 对候选池逐只精析留到后续（阶段 4
  落库 + 阶段 5 前端联调时再补）。
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage

from app.agents.utils.agent_utils import get_stock_screener

# 工具循环最多几轮（防 LLM 无限调工具卡死）
MAX_TOOL_ITERATIONS = 6

SYSTEM_PROMPT = """你是一名 A股量化选股助手。用户会用自然语言描述选股条件，你的任务是：

1. 把条件翻译成 get_stock_screener 的筛选参数（可多条件组合，未提及的参数留空即可）：
   - 「XX 行业/板块」→ industry（申万一级行业名，如 食品饮料、新能源、医药生物）
   - 「PE 低于 X」→ max_pe=X
   - 「ROE 高于 X」→ min_roe=X
   - 「净利增速高于 X / 高增长」→ min_growth=X
   - 「关注度高于 X / 人气」→ min_attention=X
   - 「换手率低于 X」→ max_turnover=X
   - 「排除 ST」→ exclude_st=True（默认就排除，除非用户明确要含 ST）
   - 「只要 N 只」→ limit=N（默认 50）
2. 先调用 get_stock_screener 拿候选列表（可能是 CSV）。
3. 基于真实返回的数据做总结：用 Markdown 表格列出前若干只候选（代码、名称、行业、
   ROE、PE、增速、关注度、换手率等关键列），并简要说明筛选口径。

要求：
- 不要编造数据，只基于工具返回的 CSV 总结；若工具返回空或报错，如实说明并给建议。
- 结尾附一句风险提示：「以上为量化初筛结果，非投资建议，需结合基本面与行业研究进一步验证。」
- 用中文回答。"""


def _execute_tool_calls(result, tools_by_name: Dict[str, Any]) -> List[ToolMessage]:
    """执行 LLM 这一轮请求的所有工具调用，把每个结果包装成 ToolMessage 回填。

    工具返回的观测值（CSV 文本）会作为 tool 消息追加到对话里，供 LLM 下一轮总结。
    """
    tool_messages = []
    for tc in result.tool_calls:
        fn = tools_by_name[tc["name"]]
        observation = fn.invoke(tc["args"])
        tool_messages.append(
            ToolMessage(content=str(observation), tool_call_id=tc["id"], name=tc["name"])
        )
    return tool_messages


def create_screener_agent(llm) -> Callable[[str], str]:
    """返回一个 run(query) 函数：输入自然语言选股条件，输出候选池总结文本。"""

    llm_with_tools = llm.bind_tools([get_stock_screener])
    tools_by_name = {get_stock_screener.name: get_stock_screener}

    def run(query: str) -> str:
        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=query),
        ]

        for _ in range(MAX_TOOL_ITERATIONS):
            result = llm_with_tools.invoke(messages)
            messages.append(result)

            # 不再请求调工具 → 说明它已经总结完了，返回最终文本
            if not result.tool_calls:
                return result.content

            # 执行工具并把观测值回填，继续下一轮
            messages.extend(_execute_tool_calls(result, tools_by_name))

        # 兜底：轮数用尽仍未收敛，返回最后一轮文本
        return result.content

    return run
