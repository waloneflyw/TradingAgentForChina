# -*- coding: utf-8 -*-
"""金融助手的轻量工具（@tool 薄壳）：search_stock + get_quote + retrieve_history。

供 app/agents/assistant.py 的 router 绑定，日常问答时按需调用。
- search_stock / get_quote 实现见 app/dataflows/assistant_data.py
- retrieve_history 检索历史分析报告（全局知识库），实现见 app/api/store.py
"""
from __future__ import annotations

from typing import Annotated, Optional

from langchain_core.tools import tool

from app.api import store
from app.dataflows import assistant_data


@tool
def search_stock(
    keyword: Annotated[str, "股票名称/代码/拼音关键字，如 茅台 / 600519 / maotai"],
) -> str:
    """按名称/代码/拼音模糊搜索 A股，返回匹配列表（代码+名称+行业+是否ST）。"""
    return assistant_data.search_stock(keyword)


@tool
def get_quote(
    ticker: Annotated[str, "股票代码，如 600519.SH 或 600519"],
) -> str:
    """获取某只 A股最新行情快照：现价/涨跌幅/PE/换手率/综合得分/关注度/人气榜排名。"""
    return assistant_data.get_quote(ticker)


@tool
def retrieve_history(
    stock_code: Annotated[Optional[str], "股票代码，如 600519.SH，查某只股票的历史报告"] = None,
    industry: Annotated[Optional[str], "申万一级行业名，如 食品饮料，查某行业的历史报告"] = None,
) -> str:
    """检索本服务曾跑出的历史分析报告（全局知识库）。返回最近若干条的元数据 + 结论摘要。

    当用户问「你之前分析过 X 吗 / 历史结论是什么 / 上次评级如何」时调用；
    stock_code 和 industry 至少给一个。
    """
    rows = store.search_reports(stock_code=stock_code, industry=industry, limit=10)
    if not rows:
        return "暂无历史报告命中（可能还没分析过该股票/行业）。"

    lines = [f"命中 {len(rows)} 条历史报告："]
    for r in rows:
        lines.append(
            f"- [{r['rating']}] {r['stock_code']} {r['stock_name'] or ''}"
            f"（{r['industry'] or '—'}，{str(r['analysis_date'])}）"
            f"结论：{(r['summary'] or '').strip()[:120]}"
        )
    return "\n".join(lines)
