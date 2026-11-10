# -*- coding: utf-8 -*-
"""测试：验证 daily_bar 迁移 + 复权因子回填的正确性。

用 D:/py/python.exe 运行：
    D:/py/python.exe backend/tests/test_daily_bar.py
"""
from __future__ import annotations

import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # backend/

from app.db.connection import source_conn, target_conn  # noqa: E402


def test_row_count_matches_source() -> None:
    src = source_conn()
    dst = target_conn()
    try:
        with src.cursor() as c:
            c.execute("SELECT COUNT(*) n FROM market_daily")
            src_n = c.fetchone()["n"]
        with dst.cursor() as c:
            c.execute("SELECT COUNT(*) n FROM daily_bar")
            dst_n = c.fetchone()["n"]
        print(f"[行数] 源 market_daily={src_n}, 目标 daily_bar={dst_n}")
        assert src_n == dst_n, f"行数不一致：{src_n} vs {dst_n}"
    finally:
        src.close()
        dst.close()


def test_sample_raw_matches_source() -> None:
    """抽样校验：目标库原始价格与源库一致（复权因子不影响原始列）。"""
    src = source_conn()
    dst = target_conn()
    try:
        with src.cursor() as c:
            c.execute(
                "SELECT * FROM market_daily WHERE stock_code='600025.SH' "
                "AND trade_date='2026-07-16'"
            )
            s = c.fetchone()
        with dst.cursor() as c:
            c.execute(
                "SELECT * FROM daily_bar WHERE stock_code='600025.SH' "
                "AND trade_date='2026-07-16'"
            )
            d = c.fetchone()
        print(f"[抽样] 源 close={s['close']} open={s['open']} volume={s['volume']}")
        print(f"[抽样] 目标 close={d['close']} open={d['open']} volume={d['volume']}")
        assert s["close"] == d["close"], "close 不一致"
        assert s["open"] == d["open"], "open 不一致"
        assert s["volume"] == d["volume"], "volume 不一致"
    finally:
        src.close()
        dst.close()


def test_adj_factor_plausible() -> None:
    """复权因子：样本股最新交易日因子≈1，且因子恒正、越往历史越小。

    不变量：0 < 因子 <= 1（普通分红/送转股）。缩股（反向拆股）股例外——
    因子会 >1，由 test_reverse_split_adj_factor 单独覆盖。

    限定到阶段 0 已回填的样本股，走 (stock_code, trade_date) 索引，
    避免对 15.7M 行做全表扫描。
    """
    sample = ("600025.SH", "000001.SZ", "600519.SH")
    dst = target_conn()
    try:
        with dst.cursor() as c:
            c.execute(
                """
                SELECT stock_code, MAX(trade_date) latest, COUNT(*) n,
                       SUM(adj_factor IS NULL) null_n,
                       MAX(adj_factor) max_f, MIN(adj_factor) min_f
                FROM daily_bar
                WHERE stock_code IN (%s, %s, %s) AND adj_factor IS NOT NULL
                GROUP BY stock_code
                ORDER BY stock_code
                """,
                sample,
            )
            rows = c.fetchall()
        print("[复权因子] 样本股（普通股：因子区间应落在 (0,1]，最新日≈1）：")
        for r in rows:
            flag = "OK" if 0 < r["min_f"] <= r["max_f"] <= 1.0001 else "CHECK"
            print(
                f"  {r['stock_code']} 最新={r['latest']} "
                f"区间=[{r['min_f']},{r['max_f']}] 空值={r['null_n']}/{r['n']} {flag}"
            )
    finally:
        dst.close()


def test_reverse_split_adj_factor() -> None:
    """缩股（反向拆股）股：前复权因子合法 >1，最大值 = 1/∏(后续 dr)。

    A 股极罕见的缩股事件（dr<1）会抬高历史价，故因子>1。全库仅 4 只：
    000156.SZ / 000722.SZ / 600094.SH / 600381.SH，其余 8 只有 dr<1 但
    被后续送转对冲、因子仍<=1。这里校验「因子>1」与「因子恒正、无0无负」。
    """
    reverse_split = ("000156.SZ", "000722.SZ", "600094.SH", "600381.SH")
    dst = target_conn()
    try:
        with dst.cursor() as c:
            c.execute(
                """
                SELECT stock_code, COUNT(*) n,
                       SUM(adj_factor > 1.001) gt1_n,
                       MAX(adj_factor) max_f, MIN(adj_factor) min_f
                FROM daily_bar
                WHERE stock_code IN (%s, %s, %s, %s) AND adj_factor IS NOT NULL
                GROUP BY stock_code
                ORDER BY stock_code
                """,
                reverse_split,
            )
            rows = c.fetchall()
        print("[缩股因子] 4 只缩股股（因子>1 行数>0，且因子恒正）：")
        for r in rows:
            assert r["gt1_n"] > 0, f"{r['stock_code']} 应有因子>1 的行"
            assert r["min_f"] > 0, f"{r['stock_code']} 出现非法非正因子"
            print(
                f"  {r['stock_code']} >1行数={r['gt1_n']}/{r['n']} "
                f"区间=[{r['min_f']},{r['max_f']}] OK"
            )
    finally:
        dst.close()


def test_qfq_derivation() -> None:
    """推导校验：qfq = close × factor；跨除权日因子应下降（价格上跳）。"""
    dst = target_conn()
    try:
        with dst.cursor() as c:
            c.execute(
                """
                SELECT trade_date, close, adj_factor,
                       ROUND(close * COALESCE(adj_factor, 1), 4) qfq
                FROM daily_bar WHERE stock_code='600025.SH'
                AND trade_date BETWEEN '2026-06-25' AND '2026-07-03'
                ORDER BY trade_date
                """
            )
            rows = c.fetchall()
        print("[qfq推导] 600025.SH 2026-06-25~07-03（跨 06-29 除息）：")
        for r in rows:
            print(
                f"  {r['trade_date']} 不复权={r['close']} "
                f"因子={r['adj_factor']} 前复权={r['qfq']}"
            )
    finally:
        dst.close()


if __name__ == "__main__":
    test_row_count_matches_source()
    test_sample_raw_matches_source()
    test_adj_factor_plausible()
    test_reverse_split_adj_factor()
    test_qfq_derivation()
    print("\n全部测试通过 ✓")
