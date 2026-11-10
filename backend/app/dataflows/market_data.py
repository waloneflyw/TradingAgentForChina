# -*- coding: utf-8 -*-
"""行情类工具实现：get_stock_data（K线）、get_indicators（技术指标）。

返回格式统一为「给 LLM 读」的格式化字符串（CSV / 带标题文本）。
"""
from __future__ import annotations

from datetime import datetime

import pandas as pd

from app.dataflows import kline
from app.dataflows.symbols import to_suffix


def get_stock_data(symbol: str, start_date: str, end_date: str, period: str = "daily") -> str:
    """K 线：日线查库（缺则拉），周/月线由日线聚合。返回前复权 OHLCV CSV。"""
    code = to_suffix(symbol)
    df = kline.load_qfq_kline(code, start_date, end_date)
    if df.empty:
        return f"无 {code} 在 {start_date}~{end_date} 的行情数据。"

    if period in ("weekly", "w", "周"):
        df = _resample(df, "W-FRI")
    elif period in ("monthly", "m", "月"):
        df = _resample(df, "M")

    out = df.copy()
    out["date"] = out["date"].dt.strftime("%Y-%m-%d")
    for c in ("open", "high", "low", "close"):
        out[c] = out[c].round(2)
    csv = out.to_csv(index=False)
    header = (
        f"# {code} 前复权K线（{period}） {start_date}~{end_date}\n"
        f"# 记录数：{len(out)}，价已前复权（不复权价=前复权价/adj_factor）\n"
        f"# 获取时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    )
    return header + csv


def _resample(df: pd.DataFrame, rule: str) -> pd.DataFrame:
    """日线聚合为周/月线。"""
    g = df.set_index("date").resample(rule).agg({
        "open": "first", "high": "max", "low": "min", "close": "last",
        "volume": "sum", "amount": "sum",
    }).dropna(subset=["open"])
    g["adj_factor"] = 1.0  # 聚合后无单日因子，语义保留占位
    return g.reset_index()


def get_indicators(symbol: str, indicator: str, curr_date: str, look_back_days: int = 30) -> str:
    """技术指标（stockstats 现算，数据源为 MySQL 前复权 K 线）。"""
    code = to_suffix(symbol)
    indicators = [i.strip() for i in indicator.split(",") if i.strip()]
    results = []
    for ind in indicators:
        try:
            results.append(kline.compute_indicator(code, ind, curr_date, look_back_days))
        except ValueError as e:
            results.append(str(e))
    return "\n\n".join(results)
