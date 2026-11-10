# -*- coding: utf-8 -*-
"""一次性脚本：回填 daily_bar.adj_factor（前复权因子）

因子定义：adj_factor = 前复权收盘价 / 不复权收盘价（最新交易日 = 1）。
推导：
  前复权价 = 不复权价 × adj_factor
  后复权价 = 不复权价 × adj_factor / MIN(adj_factor)

算法（关键）：不用 xtquant 的 front/none 相除——那对「送转股」会算出负数
（如贵州茅台 10转10 后 front 价累积失真为负，实测 2001 年 front=-312）。
改用 get_divid_factors 返回的每次除权事件复权因子 dr（恒为正的乘法因子）：

  adj_factor(t) = 1 / ∏(dr_i | 除权日 > t)

这是标准复权因子算法（tushare 的 adj_factor 同源），且只需拉取稀疏事件
（每只股票约几十条），比下载全套日线快几个数量级。

用法（必须用 D:/py/python.exe）：
  回填全部：  D:/py/python.exe backend/scripts/migrate/backfill_adj_factor.py
  回填指定：  D:/py/python.exe backend/scripts/migrate/backfill_adj_factor.py --codes 600025.SH,000001.SZ
  回填前N只： D:/py/python.exe backend/scripts/migrate/backfill_adj_factor.py --limit 10
"""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # backend/

import numpy as np  # noqa: E402

from app.db.connection import target_conn  # noqa: E402
from xtquant import xtdata  # noqa: E402


def iter_codes(conn, codes: str, limit: int) -> list[str]:
    if codes:
        return [c.strip() for c in codes.split(",") if c.strip()]
    with conn.cursor() as cur:
        if limit:
            cur.execute(
                "SELECT DISTINCT stock_code FROM daily_bar "
                "ORDER BY stock_code LIMIT %s", (limit,)
            )
        else:
            cur.execute(
                "SELECT DISTINCT stock_code FROM daily_bar ORDER BY stock_code"
            )
        return [r["stock_code"] for r in cur.fetchall()]


def stock_trade_dates(conn, code: str) -> list[str]:
    """该股票在 daily_bar 中的交易日（'YYYYMMDD' 升序）。"""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT trade_date FROM daily_bar WHERE stock_code=%s ORDER BY trade_date",
            (code,),
        )
        # trade_date 是 DATE 列，pymysql 返回 datetime.date，Python 侧格式化避开 % 转义
        return [r["trade_date"].strftime("%Y%m%d") for r in cur.fetchall()]


def is_done(conn, code: str) -> bool:
    """该股票最新交易日已有 adj_factor 即视为已回填（本脚本按整只股票全量写入）。"""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT adj_factor FROM daily_bar WHERE stock_code=%s "
            "ORDER BY trade_date DESC LIMIT 1", (code,),
        )
        row = cur.fetchone()
        return row is not None and row["adj_factor"] is not None


def adj_factor_map(code: str, trade_dates: list[str]) -> dict[str, float]:
    """返回 {trade_date('YYYYMMDD') -> adj_factor(float)}。

    无除权事件（或无数据）时返回空 dict，调用方留 NULL（查询端按 1 处理）。
    """
    ev = xtdata.get_divid_factors(code, "19900101", "20261231")
    if ev is None or ev.empty:
        return {}

    ev = ev.sort_index()
    event_dates = np.array(ev.index.tolist())          # 'YYYYMMDD' 升序
    drs = ev["dr"].astype(float).to_numpy()
    if not np.all(np.isfinite(drs)) or np.any(drs <= 0):
        raise ValueError(f"dr 含非法值：{drs.tolist()}")

    n = len(drs)
    # suffix[k] = drs[k] * drs[k+1] * ... * drs[n-1]
    suffix = np.ones(n + 1)
    for k in range(n - 1, -1, -1):
        suffix[k] = suffix[k + 1] * drs[k]

    # k = 第一个除权日 > trade_date 的下标（side='right' 跳过相等日，即除权日当天因子不含本次）
    k = np.searchsorted(event_dates, np.array(trade_dates), side="right")
    factors = 1.0 / suffix[k]
    return {d: float(v) for d, v in zip(trade_dates, factors)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--codes", default="", help="逗号分隔的股票代码")
    ap.add_argument("--limit", type=int, default=0, help="只回填前 N 只（0=全部）")
    ap.add_argument(
        "--skip-done", action=argparse.BooleanOptionalAction, default=True,
        help="跳过已回填的股票（断点续跑）；用 --no-skip-done 强制全部重做",
    )
    args = ap.parse_args()

    conn = target_conn()
    codes = iter_codes(conn, args.codes, args.limit)
    preview = codes[:20] + (["..."] if len(codes) > 20 else [])
    print(f"待回填 {len(codes)} 只：{preview}")

    ok = no_event = fail = skipped = 0
    try:
        for i, code in enumerate(codes, 1):
            try:
                if args.skip_done and is_done(conn, code):
                    skipped += 1
                    continue
                dates = stock_trade_dates(conn, code)
                if not dates:
                    print(f"  [{i}/{len(codes)}] {code}: daily_bar 无数据，跳过")
                    continue
                fac = adj_factor_map(code, dates)
                if not fac:
                    no_event += 1
                    print(f"  [{i}/{len(codes)}] {code}: 无除权事件（因子视为1，留 NULL）")
                    continue
                rows = [
                    (code, date(int(d[:4]), int(d[4:6]), int(d[6:8])), v)
                    for d, v in fac.items()
                ]
                placeholders = ", ".join(["(%s, %s, %s)"] * len(rows))
                flat = [x for r in rows for x in r]
                # 多行 upsert：一次写完整只股票，幂等覆盖（比逐行 UPDATE 快几个数量级）
                with conn.cursor() as cur:
                    cur.execute(
                        "INSERT INTO daily_bar (stock_code, trade_date, adj_factor) "
                        f"VALUES {placeholders} "
                        "ON DUPLICATE KEY UPDATE adj_factor = VALUES(adj_factor)",
                        flat,
                    )
                conn.commit()
                ok += 1
                if i % 100 == 0 or i == len(codes):
                    print(f"  [{i}/{len(codes)}] {code}: 回填 {len(fac)} 个交易日因子")
            except Exception as e:  # noqa: BLE001
                conn.rollback()
                fail += 1
                print(f"  [{i}/{len(codes)}] {code}: 失败 {type(e).__name__}: {e}")
    finally:
        conn.close()
    print(f"完成：成功 {ok}，无除权 {no_event}，失败 {fail}，跳过已回填 {skipped}")


if __name__ == "__main__":
    main()
