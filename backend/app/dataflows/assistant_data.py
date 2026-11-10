# -*- coding: utf-8 -*-
"""金融助手专用数据函数：search_stock（代码/名称/拼音联想）+ get_quote（行情快照）。

数据来源（都走 target_conn / ashare_agent，只读）：
- search_stock → stock_info（stock_code/name/pinyin/industry_sw_l1/is_st）
- get_quote    → stock_snapshot（latest_price/pct_change/pe/turnover_rate/composite_score/…）

结构化变体（search_stocks / get_quote_row）返回 dict，供阶段 5 前端 REST 端点复用；
文本变体（search_stock / get_quote）拼成字符串，供金融助手 tool 调用。SQL 只写一份。
"""
from __future__ import annotations

from app.dataflows.symbols import to_suffix
from app.db.connection import target_conn


def search_stocks(keyword: str, limit: int = 10) -> list[dict]:
    """按名称 / 代码 / 拼音模糊搜索 A股，返回结构化列表。空关键字返回空列表。"""
    kw = (keyword or "").strip()
    if not kw:
        return []

    conn = target_conn()
    try:
        with conn.cursor() as cur:
            # 名称、代码、拼音三路模糊匹配；代码完全命中者排最前
            cur.execute(
                "SELECT stock_code, name, pinyin, industry_sw_l1, is_st "
                "FROM stock_info "
                "WHERE stock_code LIKE %s OR name LIKE %s OR pinyin LIKE %s "
                "ORDER BY (stock_code = %s) DESC, stock_code "
                "LIMIT %s",
                (f"%{kw}%", f"%{kw}%", f"%{kw}%", kw, limit),
            )
            return cur.fetchall()
    finally:
        conn.close()


def search_stock(keyword: str, limit: int = 10) -> str:
    """按名称 / 代码 / 拼音模糊搜索 A股，返回文本列表。"""
    kw = keyword.strip()
    if not kw:
        return "请输入搜索关键字（股票名称 / 代码 / 拼音）。"

    rows = search_stocks(kw, limit)
    if not rows:
        return f"未找到与「{keyword}」匹配的股票，可换个关键词试试。"

    lines = [f"「{keyword}」匹配到 {len(rows)} 只："]
    for r in rows:
        st = "（ST 退市风险警示）" if r["is_st"] else ""
        lines.append(f"- {r['stock_code']}　{r['name']}{st}　行业：{r['industry_sw_l1'] or '—'}")
    return "\n".join(lines)


def get_quote_row(ticker: str) -> dict | None:
    """某只 A股最新行情快照（结构化），无数据返回 None。"""
    code = to_suffix(ticker)
    conn = target_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT trade_date, stock_name, latest_price, pct_change, pe, "
                "turnover_rate, composite_score, comment_rank, attention_index, hot_rank "
                "FROM stock_snapshot WHERE stock_code=%s ORDER BY trade_date DESC LIMIT 1",
                (code,),
            )
            return cur.fetchone()
    finally:
        conn.close()


def get_quote(ticker: str) -> str:
    """某只 A股最新行情快照：现价/涨跌幅/PE/换手/综合得分/关注度/人气榜。"""
    code = to_suffix(ticker)
    snap = get_quote_row(code)

    if not snap:
        return f"无 {code} 的行情快照（可能尚未落库）。"

    name = snap["stock_name"] or code
    lines = [f"# {code} {name} 行情快照（{snap['trade_date']}）"]
    lines.append(f"- 现价：{snap['latest_price']}　涨跌幅：{snap['pct_change']}%　换手率：{snap['turnover_rate']}%")
    lines.append(f"- 市盈率：{snap['pe']}（千股千评口径）")
    lines.append(f"- 综合得分：{snap['composite_score']}　关注指数：{snap['attention_index']}　排名：{snap['comment_rank']}")
    lines.append(f"- 人气榜排名：{snap['hot_rank'] if snap['hot_rank'] is not None else '未上榜'}")
    return "\n".join(lines)
