# -*- coding: utf-8 -*-
"""每日横截面快照：千股千评（全市场）+ 人气榜（top N，best-effort）→ stock_snapshot。

- 千股千评：akshare stock_comment_em（全市场约 5200 只，含综合得分/关注指数/排名/市盈率），主表。
- 人气榜：akshare stock_hot_rank_em（仅 top N，稀疏；东财偶发限流则跳过，hot_rank/hot_value 留 NULL）。
- 幂等：唯一键 (trade_date, stock_code)，同一交易日重复拉取覆盖更新。
用法（tradingagents 环境）：
    python scripts/pipeline/snapshot_fill.py
"""
from __future__ import annotations

import os
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path

os.environ.setdefault("TQDM_DISABLE", "1")  # 静音 akshare 内部 tqdm 分页进度条

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # backend/

import akshare as ak  # noqa: E402

from app.dataflows import akshare_source as src  # noqa: E402
from app.dataflows.db_writer import upsert  # noqa: E402
from app.dataflows.symbols import to_suffix  # noqa: E402
from app.db.connection import target_conn  # noqa: E402


def _num(v):
    """数值清洗：None/NaN/非数值文本 → None；其余 Decimal。"""
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, str):
        s = v.strip().replace(",", "")
        if not s:
            return None
        try:
            return Decimal(s)
        except InvalidOperation:
            return None
    try:
        d = Decimal(str(v))
    except (InvalidOperation, ValueError):
        return None
    return d if d.is_finite() else None


def _pick(row, *names):
    """按多个候选列名取值（akshare 列名可能随版本变）。"""
    for n in names:
        if n in row.index and row.get(n) is not None:
            return row.get(n)
    return None


def fill_comment(conn=None) -> int:
    """千股千评（全市场）→ stock_snapshot。返回写入行数。"""
    df = src.call(ak.stock_comment_em)
    rows = []
    trade_date = None
    for _, r in df.iterrows():
        code = _pick(r, "代码")
        if code is None:
            continue
        td = str(_pick(r, "交易日") or "").strip()
        if not td:
            continue
        td = td[:10]
        trade_date = trade_date or td
        rows.append({
            "trade_date": td,
            "stock_code": to_suffix(str(code).zfill(6)),
            "stock_name": str(_pick(r, "名称") or "") or None,
            "latest_price": _num(_pick(r, "最新价")),
            "pct_change": _num(_pick(r, "涨跌幅")),
            "turnover_rate": _num(_pick(r, "换手率")),
            "pe": _num(_pick(r, "市盈率")),
            "main_cost": _num(_pick(r, "主力成本")),
            "institution_participation": _num(_pick(r, "机构参与度")),
            "composite_score": _num(_pick(r, "综合得分")),
            "score_change": _num(_pick(r, "上升")),
            "comment_rank": _num(_pick(r, "目前排名")),
            "attention_index": _num(_pick(r, "关注指数")),
        })
    n = upsert("stock_snapshot", rows, ["trade_date", "stock_code"], conn=conn)
    print(f"[千股千评] 交易日={trade_date} 股票={len(rows)} 落库={n}")
    return n


def fill_hot_rank(conn=None) -> int:
    """人气榜（top N）→ 补 hot_rank/hot_value（best-effort，限流则跳过）。"""
    try:
        df = src.call(ak.stock_hot_rank_em, retries=1)
    except Exception as e:  # noqa: BLE001
        print(f"[人气榜] 跳过（源限流/异常）：{type(e).__name__}: {str(e)[:80]}")
        return 0
    if df is None or len(df) == 0:
        print("[人气榜] 空表，跳过")
        return 0

    def col(row, *names):
        for n in names:
            if n in row.index:
                return row.get(n)
        return None

    rows = []
    for _, r in df.iterrows():
        code = col(r, "代码", "股票代码")
        if code is None:
            continue
        # 人气榜给的是最新交易日，用当前数据里已有快照日期对齐（若库内无该日则跳过）
        code = str(code).zfill(6)
        rows.append({
            "stock_code": to_suffix(code),
            "hot_rank": _num(col(r, "排名", "当前排名")),
            "hot_value": _num(col(r, "热度值", "热度", "关注度")),
        })
    # 补列：按 stock_code 找到当日快照，回填 hot_rank/hot_value
    if rows:
        with conn.cursor() as cur:
            for r in rows:
                if r["hot_rank"] is None and r["hot_value"] is None:
                    continue
                cur.execute(
                    "UPDATE stock_snapshot SET hot_rank=%s, hot_value=%s "
                    "WHERE stock_code=%s AND trade_date=(SELECT MAX(trade_date) FROM stock_snapshot)",
                    (r["hot_rank"], r["hot_value"], r["stock_code"]),
                )
        conn.commit()
    print(f"[人气榜] 解析 {len(rows)} 只（未上榜/未命中交易日的不更新）")
    return len(rows)


def main() -> None:
    src.require("stock_comment_em")
    conn = target_conn()
    try:
        fill_comment(conn=conn)
        conn.commit()
        fill_hot_rank(conn=conn)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
