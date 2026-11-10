# -*- coding: utf-8 -*-
"""舆情/公告/股东工具实现。

- get_news：查 news 表，缺则 akshare 东财个股新闻拉取落库。
- get_announcements：查 announcement 表，缺则巨潮 cninfo 拉取落库。
- get_shareholder_changes：股东增减持（东财高管增减持）+ 龙虎榜，运行时拉取不落库。
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta

os.environ.setdefault("TQDM_DISABLE", "1")

from app.dataflows import akshare_source as src  # noqa: E402
from app.dataflows import cninfo  # noqa: E402
from app.dataflows.db_writer import upsert  # noqa: E402
from app.dataflows.symbols import to_bare, to_suffix  # noqa: E402
from app.db.connection import target_conn  # noqa: E402


def get_news(ticker: str, start_date: str, end_date: str) -> str:
    """个股新闻（查库 → 缺则拉）。返回标题/时间/来源列表文本。"""
    code = to_suffix(ticker)
    conn = target_conn()
    try:
        rows = _query_news(conn, code, start_date, end_date)
        if not rows:
            _fetch_stock_news(code, conn=conn)  # 东财个股新闻拉取+落库
            conn.commit()
            rows = _query_news(conn, code, start_date, end_date)
    finally:
        conn.close()

    if not rows:
        return f"无 {code} 在 {start_date}~{end_date} 的个股新闻。"
    lines = [f"# {code} 个股新闻（{len(rows)} 条）"]
    for r in rows:
        t = r["publish_time"].strftime("%Y-%m-%d %H:%M") if r["publish_time"] else "—"
        lines.append(f"- [{t}]（{r['source']}）{r['title']}")
        if r["url"]:
            lines.append(f"  {r['url']}")
    return "\n".join(lines)


def _query_news(conn, code: str, start_date: str, end_date: str):
    with conn.cursor() as cur:
        cur.execute(
            "SELECT title, source, url, publish_time FROM news "
            "WHERE stock_code=%s AND publish_time BETWEEN %s AND %s "
            "ORDER BY publish_time DESC LIMIT 50",
            (code, start_date, end_date))
        return cur.fetchall()


def _fetch_stock_news(code: str, conn=None) -> int:
    """东财个股新闻 → news（列名随版本变，best-effort）。"""
    import hashlib
    import akshare as ak

    bare = to_bare(code)
    df = src.call(ak.stock_news_em, symbol=bare)
    if df is None or len(df) == 0:
        return 0
    cols = list(df.columns)
    rows = []
    for _, r in df.iterrows():
        title = str(_pick(r, cols, "新闻标题", "标题") or "")
        if not title:
            continue
        url = str(_pick(r, cols, "新闻链接", "链接", "url") or "")
        if not url:
            url = f"https://emweb.securities.eastmoney.com/news/{hashlib.md5(title.encode()).hexdigest()[:16]}"
        pub_raw = _pick(r, cols, "发布时间", "时间", "发布日期")
        pub = None
        if pub_raw:
            try:
                pub = datetime.strptime(str(pub_raw)[:19], "%Y-%m-%d %H:%M:%S")
            except Exception:
                pub = None
        rows.append({
            "stock_code": code, "source": "eastmoney", "url": url[:500],
            "title": title[:500],
            "content": str(_pick(r, cols, "新闻内容", "内容") or "") or None,
            "publish_time": pub or datetime.now(),
        })
    return upsert("news", rows, ["source", "url"], conn=conn)


def get_announcements(ticker: str, start_date: str, end_date: str) -> str:
    """公告列表（查库 → 缺则巨潮拉取）。返回标题/时间/类别/链接。"""
    code = to_suffix(ticker)
    conn = target_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT title, url, announce_time, category FROM announcement "
                "WHERE stock_code=%s AND announce_time BETWEEN %s AND %s "
                "ORDER BY announce_time DESC LIMIT 100",
                (code, start_date, end_date))
            rows = cur.fetchall()
        if not rows:
            anns = cninfo.fetch_announcements(code, start_date, end_date)
            upsert("announcement", [{
                "stock_code": a["stock_code"], "title": a["title"], "url": a["url"],
                "announce_time": a["announce_time"], "category": a["category"],
            } for a in anns if a["announce_time"]], ["url"], conn=conn)
            conn.commit()
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT title, url, announce_time, category FROM announcement "
                    "WHERE stock_code=%s AND announce_time BETWEEN %s AND %s "
                    "ORDER BY announce_time DESC LIMIT 100",
                    (code, start_date, end_date))
                rows = cur.fetchall()
    finally:
        conn.close()

    if not rows:
        return f"无 {code} 在 {start_date}~{end_date} 的公告。"
    lines = [f"# {code} 公告列表（{len(rows)} 条）"]
    for r in rows:
        t = r["announce_time"].strftime("%Y-%m-%d") if r["announce_time"] else "—"
        cat = f"（{r['category']}）" if r["category"] else ""
        lines.append(f"- [{t}]{cat} {r['title']}")
        if r["url"]:
            lines.append(f"  {r['url']}")
    return "\n".join(lines)


def get_shareholder_changes(ticker: str) -> str:
    """股东增减持（东财高管增减持）+ 龙虎榜。运行时拉取，返回文本。

    akshare 这两个接口都是「全市场按条件返回」，无逐股参数，故拉全量后按代码过滤。
    """
    import akshare as ak

    code = to_suffix(ticker)
    bare = to_bare(code)
    parts = [f"# {code} 股东变动 / 龙虎榜（运行时拉取）"]

    # 1) 高管/股东增减持（stock_ggcg_em 的 symbol 是「股东类型」而非代码，取全部再过滤）
    try:
        gg = src.call(ak.stock_ggcg_em, symbol="全部", retries=1)
        if gg is not None and len(gg):
            cols = list(gg.columns)
            code_col = "代码" if "代码" in cols else ("股票代码" if "股票代码" in cols else None)
            if code_col:
                gg = gg[gg[code_col].astype(str).str.zfill(6) == bare]
            if len(gg):
                gg = gg.head(10)
                lines = ["\n【高管/股东增减持（东财，最近 10 条）】"]
                for _, r in gg.iterrows():
                    name = _pick(r, cols, "股东名称", "变动人", "名称") or "—"
                    dt = _pick(r, cols, "公告日", "变动截止日", "变动开始日") or "—"
                    chg = _pick(r, cols, "持股变动信息-变动数量") or "—"
                    pct = _pick(r, cols, "持股变动信息-占总股本比例") or "—"
                    why = _pick(r, cols, "持股变动信息-增减") or "—"
                    lines.append(f"- [{dt}] {name}：{why} {chg} 万股（占总股本 {pct}%）")
                parts.append("\n".join(lines))
            else:
                parts.append("\n【高管/股东增减持】近期无该股记录")
        else:
            parts.append("\n【高管/股东增减持】无数据")
    except Exception as e:  # noqa: BLE001
        parts.append(f"\n【高管/股东增减持】拉取失败：{type(e).__name__}")

    # 2) 龙虎榜（stock_lhb_detail_em 按日期范围返回，再按代码过滤）
    try:
        start = (datetime.now() - timedelta(days=30)).strftime("%Y%m%d")
        end = datetime.now().strftime("%Y%m%d")
        lhb = src.call(ak.stock_lhb_detail_em, start_date=start, end_date=end, retries=1)
        if lhb is not None and len(lhb):
            cols = list(lhb.columns)
            code_col = "代码" if "代码" in cols else ("股票代码" if "股票代码" in cols else None)
            if code_col:
                lhb = lhb[lhb[code_col].astype(str).str.zfill(6) == bare]
            if len(lhb):
                lhb = lhb.head(10)
                lines = ["\n【龙虎榜（东财，近 30 日）】"]
                for _, r in lhb.iterrows():
                    dt = _pick(r, cols, "上榜日", "日期") or "—"
                    reason = _pick(r, cols, "上榜原因", "解读") or "—"
                    buy = _pick(r, cols, "龙虎榜买入额") or "—"
                    sell = _pick(r, cols, "龙虎榜卖出额") or "—"
                    net = _pick(r, cols, "龙虎榜净买额") or "—"
                    lines.append(f"- [{dt}] 买 {buy} / 卖 {sell} / 净 {net}（{reason}）")
                parts.append("\n".join(lines))
            else:
                parts.append("\n【龙虎榜】近 30 日无该股记录")
        else:
            parts.append("\n【龙虎榜】无数据")
    except Exception as e:  # noqa: BLE001
        parts.append(f"\n【龙虎榜】拉取失败：{type(e).__name__}")

    return "\n".join(parts)


def _pick(row, cols, *names):
    for n in names:
        if n in cols and row.get(n) is not None and str(row.get(n)) not in ("", "nan", "None"):
            return row.get(n)
    return None
