# -*- coding: utf-8 -*-
"""A股版工具（@tool 薄壳）。

每个 @tool 只做参数转发给 route()，真正实现见 app/dataflows/*。工具名/参数
与文档阶段 2 的 A股工具清单一致，供阶段 3 分析师 agent 通过 tool-calling 绑定。
"""
from __future__ import annotations

from typing import Annotated, Optional

from langchain_core.tools import tool

from app.dataflows.interface import route


@tool
def get_stock_data(
    symbol: Annotated[str, "股票代码，如 600519.SH 或 600519"],
    start_date: Annotated[str, "起始日 yyyy-mm-dd"],
    end_date: Annotated[str, "结束日 yyyy-mm-dd"],
    period: Annotated[str, "周期：daily/weekly/monthly（默认 daily）"] = "daily",
) -> str:
    """获取某只 A股在指定日期区间的 K 线（前复权 OHLCV，CSV 格式）。"""
    return route("get_stock_data", symbol, start_date, end_date, period)


@tool
def get_indicators(
    symbol: Annotated[str, "股票代码，如 600519.SH"],
    indicator: Annotated[str, "技术指标名，如 rsi/macd/boll/close_50_sma，可逗号分隔多个"],
    curr_date: Annotated[str, "当前交易日 yyyy-mm-dd"],
    look_back_days: Annotated[int, "回看天数，默认 30"] = 30,
) -> str:
    """计算单个/多个技术指标（stockstats 现算，基于前复权 K 线）。"""
    return route("get_indicators", symbol, indicator, curr_date, look_back_days)


@tool
def get_fundamentals(
    ticker: Annotated[str, "股票代码，如 600519.SH"],
    curr_date: Annotated[str, "当前日期 yyyy-mm-dd"],
) -> str:
    """获取公司基本面概况：行业、估值、盈利/成长指标、现价与关注度。"""
    return route("get_fundamentals", ticker, curr_date)


@tool
def get_financial_statements(
    ticker: Annotated[str, "股票代码，如 600519.SH"],
    statement_type: Annotated[str, "报表类型：balance/income/cashflow/all（默认 all）"] = "all",
    freq: Annotated[str, "报告频率：quarterly/annual（默认 quarterly）"] = "quarterly",
) -> str:
    """获取三大财务报表（资产负债表/利润表/现金流量表，宽表 CSV）。"""
    return route("get_financial_statements", ticker, statement_type, freq)


@tool
def get_news(
    ticker: Annotated[str, "股票代码，如 600519.SH"],
    start_date: Annotated[str, "起始日 yyyy-mm-dd"],
    end_date: Annotated[str, "结束日 yyyy-mm-dd"],
) -> str:
    """获取个股新闻（标题/时间/来源/链接列表）。"""
    return route("get_news", ticker, start_date, end_date)


@tool
def get_announcements(
    ticker: Annotated[str, "股票代码，如 600519.SH"],
    start_date: Annotated[str, "起始日 yyyy-mm-dd"],
    end_date: Annotated[str, "结束日 yyyy-mm-dd"],
) -> str:
    """获取公司公告列表（标题/时间/类别/链接）。"""
    return route("get_announcements", ticker, start_date, end_date)


@tool
def get_shareholder_changes(
    ticker: Annotated[str, "股票代码，如 600519.SH"],
) -> str:
    """获取股东/高管增减持与龙虎榜数据（对应美股 insider transactions）。"""
    return route("get_shareholder_changes", ticker)


@tool
def get_market_overview(
    curr_date: Annotated[str, "当前日期 yyyy-mm-dd"],
) -> str:
    """获取大盘概览：核心指数、行业板块涨跌、北向资金。"""
    return route("get_market_overview", curr_date)


@tool
def get_stock_screener(
    industry: Annotated[Optional[str], "申万一级行业名，模糊匹配，如 食品饮料"] = None,
    min_roe: Annotated[Optional[float], "最低 ROE(%)"] = None,
    max_pe: Annotated[Optional[float], "最高市盈率(倍，>0)"] = None,
    min_growth: Annotated[Optional[float], "最低净利同比增速(%)"] = None,
    min_attention: Annotated[Optional[float], "最低关注指数"] = None,
    max_turnover: Annotated[Optional[float], "最高换手率(%)"] = None,
    exclude_st: Annotated[bool, "是否排除 ST（默认是）"] = True,
    limit: Annotated[int, "返回数量，默认 50"] = 50,
) -> str:
    """量化初筛（纯 SQL）：按行业/估值/成长/关注度/换手等条件选股，综合得分排序。"""
    return route("get_stock_screener", industry=industry, min_roe=min_roe, max_pe=max_pe,
                 min_growth=min_growth, min_attention=min_attention, max_turnover=max_turnover,
                 exclude_st=exclude_st, limit=limit)


# 供阶段 3 分析师绑定的工具清单（与文档阶段 2 的 9 工具一一对应）
ALL_TOOLS = [
    get_stock_data,
    get_indicators,
    get_fundamentals,
    get_financial_statements,
    get_news,
    get_announcements,
    get_shareholder_changes,
    get_market_overview,
    get_stock_screener,
]
