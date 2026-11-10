# -*- coding: utf-8 -*-
"""大盘概览 + 量化初筛工具实现。

- get_market_overview：大盘指数 + 行业板块 + 北向资金（运行时拉取，不落库）。
- get_stock_screener：量化初筛（纯 SQL，join stock_info/financial_indicator/stock_snapshot）。
"""
from __future__ import annotations

import os

os.environ.setdefault("TQDM_DISABLE", "1")

from app.dataflows import akshare_source as src  # noqa: E402
from app.db.connection import target_conn  # noqa: E402

# 大盘核心指数（akshare stock_zh_index_spot_em 的代码）
_INDEX_CODES = {"000001": "上证指数", "399001": "深证成指", "399006": "创业板指", "000300": "沪深300"}


def get_market_overview(curr_date: str) -> str:
    """大盘概览：核心指数 + 行业板块涨跌 + 北向资金。运行时拉取。"""
    import akshare as ak

    parts = [f"# 大盘概览（{curr_date}）"]

    # 1) 核心指数
    try:
        spot = src.call(ak.stock_zh_index_spot_em, retries=1)
        cols = list(spot.columns)
        lines = ["\n【核心指数】"]
        for code, cname in _INDEX_CODES.items():
            row = spot[spot["代码"].astype(str) == code]
            if not row.empty:
                r = row.iloc[0]
                price = r.get("最新价", "—")
                pct = r.get("涨跌幅", "—")
                lines.append(f"- {cname}：{price}（{pct}%）")
        parts.append("\n".join(lines))
    except Exception as e:  # noqa: BLE001
        parts.append(f"\n【核心指数】拉取失败：{type(e).__name__}")

    # 2) 行业板块
    try:
        board = src.call(ak.stock_board_industry_name_em, retries=1)
        if board is not None and len(board):
            up = board[board["涨跌幅"] > 0]
            down = board[board["涨跌幅"] < 0]
            top = board.nlargest(5, "涨跌幅")[["板块名称", "涨跌幅"]]
            bot = board.nsmallest(5, "涨跌幅")[["板块名称", "涨跌幅"]]
            lines = [f"\n【行业板块】上涨 {len(up)} / 下跌 {len(down)}"]
            lines.append("涨幅前5：" + "、".join(f"{r['板块名称']}({r['涨跌幅']}%)" for _, r in top.iterrows()))
            lines.append("跌幅前5：" + "、".join(f"{r['板块名称']}({r['涨跌幅']}%)" for _, r in bot.iterrows()))
            parts.append("\n".join(lines))
    except Exception as e:  # noqa: BLE001
        parts.append(f"\n【行业板块】拉取失败：{type(e).__name__}")

    # 3) 北向资金（沪深港通）
    try:
        hsgt = src.call(ak.stock_hsgt_fund_flow_summary_em, retries=1)
        if hsgt is not None and len(hsgt):
            hsgt = hsgt.head(6)
            lines = ["\n【北向/沪深港通资金（亿元）】"]
            for _, r in hsgt.iterrows():
                lines.append(f"- {_v(r, '交易日', '日期')}：{_v(r, '资金方向', '类型')} {_v(r, '成交净买额', '当日资金流入', '净买额')}")
            parts.append("\n".join(lines))
    except Exception as e:  # noqa: BLE001
        parts.append(f"\n【北向资金】拉取失败：{type(e).__name__}")

    return "\n".join(parts)


def _v(row, *names):
    for n in names:
        if n in row.index and row.get(n) is not None and str(row.get(n)) not in ("", "nan", "None"):
            return row.get(n)
    return "—"


def screener_rows(
    industry: str | None = None,
    min_roe: float | None = None,
    max_pe: float | None = None,
    min_growth: float | None = None,
    min_attention: float | None = None,
    max_turnover: float | None = None,
    exclude_st: bool = True,
    limit: int = 50,
) -> list[dict]:
    """量化初筛（纯 SQL，结构化）。join 三张落库表，按条件 WHERE，综合得分排序。

    所有条件均 NULL 表示不限制；命中结果按 stock_snapshot 综合得分降序。
    供阶段 5 前端选股表格复用；get_stock_screener 在此之上拼文本给助手。
    """
    where = []
    params: list = []

    if exclude_st:
        where.append("si.is_st = 0")
    if industry:
        where.append("si.industry_sw_l1 LIKE %s")
        params.append(f"%{industry}%")
    if min_roe is not None:
        where.append("fi.roe >= %s")
        params.append(min_roe)
    if max_pe is not None:
        where.append("ss.pe > 0 AND ss.pe <= %s")
        params.append(max_pe)
    if min_growth is not None:
        where.append("fi.net_profit_growth >= %s")
        params.append(min_growth)
    if min_attention is not None:
        where.append("ss.attention_index >= %s")
        params.append(min_attention)
    if max_turnover is not None:
        where.append("ss.turnover_rate <= %s")
        params.append(max_turnover)

    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    sql = f"""
    SELECT si.stock_code, si.name, si.industry_sw_l1,
           fi.roe, fi.net_profit_growth, fi.gross_margin,
           ss.latest_price, ss.pct_change, ss.pe, ss.turnover_rate,
           ss.composite_score, ss.attention_index, ss.comment_rank
    FROM stock_info si
    LEFT JOIN (
        SELECT fi.* FROM financial_indicator fi
        JOIN (SELECT stock_code, MAX(report_date) rd FROM financial_indicator GROUP BY stock_code) m
          ON fi.stock_code=m.stock_code AND fi.report_date=m.rd
    ) fi ON fi.stock_code = si.stock_code
    LEFT JOIN (
        SELECT ss.* FROM stock_snapshot ss
        JOIN (SELECT stock_code, MAX(trade_date) td FROM stock_snapshot GROUP BY stock_code) m
          ON ss.stock_code=m.stock_code AND ss.trade_date=m.td
    ) ss ON ss.stock_code = si.stock_code
    {where_sql}
    ORDER BY ss.composite_score DESC
    LIMIT %s
    """
    params.append(limit)

    conn = target_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall()
    finally:
        conn.close()


def get_stock_screener(
    industry: str | None = None,
    min_roe: float | None = None,
    max_pe: float | None = None,
    min_growth: float | None = None,
    min_attention: float | None = None,
    max_turnover: float | None = None,
    exclude_st: bool = True,
    limit: int = 50,
) -> str:
    """量化初筛（文本版，供助手 tool 用）。条件同 screener_rows。"""
    rows = screener_rows(
        industry=industry, min_roe=min_roe, max_pe=max_pe, min_growth=min_growth,
        min_attention=min_attention, max_turnover=max_turnover,
        exclude_st=exclude_st, limit=limit,
    )

    if not rows:
        return "量化初筛无命中（可能数据未落库或条件过严）。"

    conds = []
    if industry:
        conds.append(f"行业={industry}")
    for label, v in (("ROE≥", min_roe), ("PE≤", max_pe), ("净利增速≥", min_growth),
                     ("关注≥", min_attention), ("换手≤", max_turnover)):
        if v is not None:
            conds.append(f"{label}{v}")
    head = "# 量化初筛结果" + (f"（{', '.join(conds)}）" if conds else "")
    lines = [head, f"共 {len(rows)} 只："]
    for r in rows:
        lines.append(
            f"- {r['stock_code']} {r['name']}｜{r['industry_sw_l1'] or '—'}｜"
            f"ROE {r['roe'] or '—'}%｜净利增速 {r['net_profit_growth'] or '—'}%｜"
            f"PE {r['pe'] or '—'}｜现价 {r['latest_price'] or '—'}｜综合得分 {r['composite_score'] or '—'}"
        )
    return "\n".join(lines)
