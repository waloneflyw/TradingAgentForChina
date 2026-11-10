# -*- coding: utf-8 -*-
"""基本面工具实现：get_fundamentals（概况+估值）、get_financial_statements（三大报表）。

数据来源：stock_info（行业/名称/ST）、financial_indicator（成长/盈利）、
stock_snapshot（PE/现价/关注度）、financial_statement（三大报表竖表）。
"""
from __future__ import annotations

from app.dataflows.symbols import to_suffix
from app.db.connection import target_conn

_STATEMENT_CN = {"balance": "资产负债表", "income": "利润表", "cashflow": "现金流量表"}


def get_fundamentals(ticker: str, curr_date: str) -> str:
    """公司概况：行业 + 估值 + 盈利/成长 + 现价/关注度。"""
    code = to_suffix(ticker)
    conn = target_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT name, industry_sw_l1, industry_sw_l2, is_st, list_date "
                "FROM stock_info WHERE stock_code=%s", (code,))
            info = cur.fetchone()
            cur.execute(
                "SELECT report_date, roe, roa, eps, revenue_growth, net_profit_growth, "
                "gross_margin, net_margin, pe, pb, dividend_yield, total_market_cap "
                "FROM financial_indicator WHERE stock_code=%s ORDER BY report_date DESC LIMIT 1",
                (code,))
            ind = cur.fetchone()
            cur.execute(
                "SELECT trade_date, latest_price, pct_change, pe, turnover_rate, "
                "composite_score, comment_rank, attention_index "
                "FROM stock_snapshot WHERE stock_code=%s ORDER BY trade_date DESC LIMIT 1",
                (code,))
            snap = cur.fetchone()
    finally:
        conn.close()

    if not info:
        return f"未找到 {code} 的基础信息。"

    name = info["name"] or code
    lines = [f"# {code} {name} 基本面概况"]
    if info["is_st"]:
        lines.append("⚠ 该股为 ST/*ST，退市风险警示。")
    lines.append(f"- 行业：{info['industry_sw_l1'] or '—'} / {info['industry_sw_l2'] or '—'}")
    lines.append(f"- 上市日：{info['list_date'] or '—'}")

    if snap:
        lines.append("\n【行情快照】" + f"（{snap['trade_date']}）")
        lines.append(f"- 现价：{snap['latest_price']}　涨跌幅：{snap['pct_change']}%　换手率：{snap['turnover_rate']}%")
        lines.append(f"- 市盈率(千股千评口径)：{snap['pe']}")
        lines.append(f"- 综合得分：{snap['composite_score']}　关注指数：{snap['attention_index']}　排名：{snap['comment_rank']}")

    if ind:
        lines.append(f"\n【财务指标】" + f"（报告期 {ind['report_date']}）")
        lines.append(f"- ROE：{ind['roe']}%　ROA：{ind['roa']}%　EPS：{ind['eps']} 元")
        lines.append(f"- 营收增速：{ind['revenue_growth']}%　净利增速：{ind['net_profit_growth']}%")
        lines.append(f"- 毛利率：{ind['gross_margin']}%　净利率：{ind['net_margin']}%")
        lines.append(f"- 市盈率：{ind['pe']}　市净率：{ind['pb']}　股息率：{ind['dividend_yield']}%　总市值：{ind['total_market_cap']}")
    else:
        lines.append("\n【财务指标】无数据（可能尚未落库）")

    return "\n".join(lines)


def get_financial_statements(ticker: str, statement_type: str = "all", freq: str = "quarterly") -> str:
    """三大报表竖表 → 宽表（report_date × 科目）返回 CSV。

    statement_type: balance/income/cashflow/all（默认 all 返回三张）。
    """
    code = to_suffix(ticker)
    types = list(_STATEMENT_CN) if statement_type == "all" else [statement_type]
    types = [t for t in types if t in _STATEMENT_CN]

    conn = target_conn()
    try:
        with conn.cursor() as cur:
            ph = ",".join(["%s"] * len(types))
            cur.execute(
                f"SELECT report_type, report_date, item_name, item_value FROM financial_statement "
                f"WHERE stock_code=%s AND report_type IN ({ph}) ORDER BY report_date DESC, report_type",
                (code, *types))
            rows = cur.fetchall()
    finally:
        conn.close()

    if not rows:
        return f"无 {code} 的财报数据（报表类型：{'/'.join(types)}）。"

    import pandas as pd
    df = pd.DataFrame(rows)
    parts = []
    for t in types:
        sub = df[df["report_type"] == t]
        if sub.empty:
            continue
        wide = sub.pivot_table(index="item_name", columns="report_date", values="item_value", aggfunc="first")
        # 只保留中文科目（过滤未映射的英文残留列），并取最近 4 个报告期（pivot 日期列升序 → 末尾最新）
        wide = wide[wide.index.str.contains(r"[一-鿿]", regex=True)]
        wide = wide.iloc[:, -4:]
        parts.append(f"# {_STATEMENT_CN[t]}（{code}，单位：元）\n{wide.to_csv()}")
    if not parts:
        return f"无 {code} 的财报数据。"
    return "\n\n".join(parts)
