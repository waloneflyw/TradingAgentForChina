# -*- coding: utf-8 -*-
"""供各 Agent 复用的「小工具函数」。

这里不负责拉数据（真正的数据工具在 app/tools/stock_tools.py），而是几个通用助手：
- get_language_instruction() —— 按配置返回「用某语言输出」的提示语
- build_instrument_context() —— 生成「这是哪个标的」的上下文提示（A股版）
- create_msg_delete()       —— 生成一个「清空消息」的节点函数（分析师之间用它防消息堆积）

同时把 stock_tools 里的工具集中 re-export，方便其它模块统一 import。
"""
from __future__ import annotations

from langchain_core.messages import HumanMessage, RemoveMessage

from app.config import Config

# 集中 re-export A股工具（对应参考项目的 *_tools.py）
from app.tools.stock_tools import (
    get_stock_data,
    get_indicators,
    get_fundamentals,
    get_financial_statements,
    get_news,
    get_announcements,
    get_shareholder_changes,
    get_market_overview,
    get_stock_screener,
)


def get_language_instruction() -> str:
    """返回「用配置语言输出」的提示语。

    English（默认）时返回空串，省 token。A股 MVP 配置为 Chinese，返回
    「用中文写全部回复」，只对面向用户的分析师/组合经理生效（内部辩论保持英文推理）。
    """
    lang = Config.OUTPUT_LANGUAGE
    if lang.strip().lower() == "english":
        return ""
    return f" Write your entire response in {lang}."


def build_instrument_context(ticker: str) -> str:
    """描述被分析的 A股标的，要求每个工具调用/报告/建议都用同一代码。

    A股代码必须带交易所后缀（.SH 上交所 / .SZ 深交所），例如 600519.SH、000001.SZ，
    否则数据层无法定位。这里把该约定写进上下文，让 LLM 别乱改代码。
    """
    return (
        f"The instrument to analyze is `{ticker}`. "
        "Use this exact ticker in every tool call, report, and recommendation. "
        "A-share tickers must carry the exchange suffix: `.SH` for Shanghai "
        "(60xxxx, 68xxxx) and `.SZ` for Shenzhen (00xxxx, 30xxxx). "
        "Never strip the suffix or convert it to a US-style ticker."
    )


def create_msg_delete():
    """返回一个「清空消息」的节点函数，供分析师之间调用。

    【为什么需要】每个分析师跑完都会往 messages 里堆大量消息（工具调用、
    工具结果、中间输出）。不清理就进下一个分析师，消息会无限膨胀，既浪费
    token 又可能超上下文。所以分析完一个就清一次：删掉所有消息，补一条
    占位消息 "Continue" 让下一位 Agent 有东西可接着跑。
    """

    def delete_messages(state):
        messages = state["messages"]

        # 把当前所有消息标记为待删除
        removal_operations = [RemoveMessage(id=m.id) for m in messages]

        # 极简占位消息（兼容对空消息敏感的模型）
        placeholder = HumanMessage(content="Continue")

        return {"messages": removal_operations + [placeholder]}

    return delete_messages
