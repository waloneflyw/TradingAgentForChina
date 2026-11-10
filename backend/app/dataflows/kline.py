# -*- coding: utf-8 -*-
"""复权 K 线加载 + akshare 缺则拉落库 + stockstats 技术指标。

本模块是 A股数据层的底层：工具函数（get_stock_data/get_indicators）都从这里拿
「前复权」OHLCV。前复权价 = 不复权价 × adj_factor（daily_bar 存不复权 + 因子）。
"""
from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("TQDM_DISABLE", "1")

import pandas as pd  # noqa: E402

from app.dataflows import akshare_source as src  # noqa: E402
from app.dataflows.db_writer import upsert  # noqa: E402
from app.dataflows.symbols import to_bare, to_suffix  # noqa: E402
from app.db.connection import target_conn  # noqa: E402

# stockstats 指标列名（懒计算）→ 中文说明，随结果返回给 LLM
INDICATOR_DESC = {
    "rsi": "RSI 相对强弱（14日）：70 以上超买、30 以下超卖，也看与价格的背离。",
    "macd": "MACD 快线（DIF）：12/26 日 EMA 之差，上穿信号线看多。",
    "macds": "MACD 信号线（DEA）：DIF 的 9 日 EMA。",
    "macdh": "MACD 柱（DIF-DEA）：柱由负转正动量转强。",
    "boll": "布林带中轨（20 日均线）。",
    "boll_ub": "布林带上轨（中轨+2σ），突破可能超买。",
    "boll_lb": "布林带下轨（中轨-2σ），跌破可能超卖。",
    "close_50_sma": "50 日均线：中期趋势与动态支撑/压力。",
    "close_200_sma": "200 日均线：长期趋势基准，金叉/死叉参考。",
    "close_10_ema": "10 日 EMA：短期动能，捕捉快速转向。",
    "close_20_sma": "20 日均线：月线级别趋势。",
    "close_5_ema": "5 日 EMA：超短期动量。",
}


def _fetch_ak_hist(bare: str, start: str, end: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """akshare 拉不复权 + 前复权日线（用于算 adj_factor）。返回 (raw, qfq)。"""
    import akshare as ak

    s, e = start.replace("-", ""), end.replace("-", "")
    raw = src.call(ak.stock_zh_a_hist, symbol=bare, period="daily", start_date=s, end_date=e, adjust="")
    qfq = src.call(ak.stock_zh_a_hist, symbol=bare, period="daily", start_date=s, end_date=e, adjust="qfq")
    return raw, qfq


def fill_missing_daily(code: str, start: str, end: str, conn=None) -> int:
    """缺则拉：akshare 拉 [start,end] 不复权 + 前复权 → 算 adj_factor → upsert daily_bar。"""
    bare = to_bare(code)
    suffix = to_suffix(code)
    raw, qfq = _fetch_ak_hist(bare, start, end)
    if raw is None or len(raw) == 0:
        return 0
    qfq_close = qfq.set_index("日期")["收盘"] if qfq is not None and len(qfq) else None
    rows = []
    for _, r in raw.iterrows():
        d = str(r["日期"])[:10]
        adj = 1.0
        if qfq_close is not None and d in qfq_close.index:
            raw_close = float(r["收盘"])
            if raw_close:
                adj = float(qfq_close[d]) / raw_close
        rows.append({
            "stock_code": suffix,
            "trade_date": d,
            "open": r.get("开盘"), "high": r.get("最高"), "low": r.get("最低"), "close": r.get("收盘"),
            "pct_chg": r.get("涨跌幅"), "amplitude": r.get("振幅"),
            "volume": r.get("成交量"), "amount": r.get("成交额"),
            "turnover_rate": r.get("换手率"),
            "adj_factor": adj,
        })
    return upsert("daily_bar", rows, ["stock_code", "trade_date"], conn=conn)


def load_qfq_kline(code: str, start: str, end: str, conn=None) -> pd.DataFrame:
    """查 daily_bar → 缺则拉落库 → 返回前复权 K 线。

    返回列：date/open/high/low/close/volume/amount/adj_factor（OHLC 均前复权）。
    """
    own = conn is None
    conn = conn or target_conn()
    try:
        suffix = to_suffix(code)
        with conn.cursor() as cur:
            cur.execute(
                "SELECT trade_date, open, high, low, close, volume, amount, adj_factor "
                "FROM daily_bar WHERE stock_code=%s AND trade_date BETWEEN %s AND %s "
                "ORDER BY trade_date",
                (suffix, start, end),
            )
            rows = cur.fetchall()
        if not rows:
            try:
                n = fill_missing_daily(code, start, end, conn=conn)
                conn.commit()
            except Exception as e:  # noqa: BLE001 —— 源限流/断连时优雅降级，返回空而非崩溃
                n = 0
                print(f"[kline] 缺则拉失败（{code} {start}~{end}）：{type(e).__name__}: {str(e)[:80]}")
            if n:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT trade_date, open, high, low, close, volume, amount, adj_factor "
                        "FROM daily_bar WHERE stock_code=%s AND trade_date BETWEEN %s AND %s "
                        "ORDER BY trade_date",
                        (suffix, start, end),
                    )
                    rows = cur.fetchall()
        if not rows:
            return pd.DataFrame()
        df = pd.DataFrame(rows)
        df["date"] = pd.to_datetime(df["trade_date"])
        factor = pd.to_numeric(df["adj_factor"], errors="coerce").fillna(1.0)
        for col in ("open", "high", "low", "close"):
            df[col] = pd.to_numeric(df[col], errors="coerce") * factor
        return df[["date", "open", "high", "low", "close", "volume", "amount", "adj_factor"]]
    finally:
        if own:
            conn.close()


def compute_indicator(code: str, indicator: str, curr_date: str, look_back_days: int = 60) -> str:
    """用前复权 K 线现算单个技术指标，返回「指标名+说明+最新值+近期序列」文本。"""
    from stockstats import wrap

    if indicator not in INDICATOR_DESC:
        # stockstats 支持但未收录说明的指标也放行，用通用说明
        desc = f"技术指标 {indicator}"
    else:
        desc = INDICATOR_DESC[indicator]

    end = curr_date
    # 往前多取一些交易日，保证 50/200 日均线等长周期指标有足够窗口
    start = (pd.to_datetime(curr_date) - pd.Timedelta(days=look_back_days * 3)).strftime("%Y-%m-%d")
    df = load_qfq_kline(code, start, end)
    if df.empty:
        return f"无 {code} 的行情数据（{start}~{end}），无法计算 {indicator}。"

    k = df.rename(columns={"volume": "volume"}).copy()
    try:
        s = wrap(k)  # stockstats 识别 date/open/high/low/close/volume
        series = s[indicator]
    except Exception as e:  # noqa: BLE001
        return f"计算 {indicator} 失败：{type(e).__name__}: {e}"

    recent = [float(v) for v in series.dropna().tail(5).tolist()]
    latest = recent[-1] if recent else None
    last_date = df["date"].iloc[-1].strftime("%Y-%m-%d")
    if latest is None:
        return f"{indicator}（{desc}）在 {last_date} 无有效值（数据不足）。"

    lines = [f"指标：{indicator}", f"说明：{desc}", f"最新值（{last_date}）：{latest:.4f}"]
    if len(recent) > 1:
        lines.append("近 5 个交易日：" + " → ".join(f"{v:.4f}" for v in recent))
    return "\n".join(lines)
