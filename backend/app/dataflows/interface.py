# -*- coding: utf-8 -*-
"""A股版数据路由层（对应参考项目 dataflows/interface.py）。

美股版在多个供应商（yfinance/alpha_vantage）间做回退；A股版是「本地库优先 →
源拉取兜底 + 落库」单一路径，因此路由简化为一张 method → 实现函数 的分发表。
Agent 层的 @tool 薄壳只调用 route(method, ...)，不感知具体数据源。
"""
from __future__ import annotations

from typing import Callable

from app.dataflows import fundamentals, market_data, market_overview, news_source

METHOD_MAP: dict[str, Callable] = {
    "get_stock_data": market_data.get_stock_data,
    "get_indicators": market_data.get_indicators,
    "get_fundamentals": fundamentals.get_fundamentals,
    "get_financial_statements": fundamentals.get_financial_statements,
    "get_news": news_source.get_news,
    "get_announcements": news_source.get_announcements,
    "get_shareholder_changes": news_source.get_shareholder_changes,
    "get_market_overview": market_overview.get_market_overview,
    "get_stock_screener": market_overview.get_stock_screener,
}


def route(method: str, *args, **kwargs) -> str:
    """把方法名分发到对应 A股数据实现，返回给 LLM 读的格式化字符串。"""
    if method not in METHOD_MAP:
        raise ValueError(f"未支持的数据方法：{method}（可用：{', '.join(METHOD_MAP)}）")
    return METHOD_MAP[method](*args, **kwargs)
