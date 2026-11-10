# -*- coding: utf-8 -*-
"""样例股票全链路落库 + 幂等验证（阶段 1 验收）。

跑两遍，对比各表行数应一致（ON DUPLICATE KEY UPDATE 幂等）。
用法（tradingagents 环境）：
    python scripts/pipeline/run_sample.py --codes 600519.SH,000001.SZ,300750.SZ
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
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))          # backend/
sys.path.insert(0, str(Path(__file__).resolve().parent))              # 同目录脚本

from app.db.connection import target_conn  # noqa: E402
from app.dataflows.symbols import to_suffix  # noqa: E402

import announcement_fill  # noqa: E402
import financial_fill  # noqa: E402
import news_fill  # noqa: E402
import stock_info_fill  # noqa: E402


def _counts(codes: list[str]) -> dict:
    conn = target_conn()
    try:
        ph = ",".join(["%s"] * len(codes))
        out = {}
        with conn.cursor() as cur:
            for table in ("stock_info", "financial_statement", "financial_indicator", "announcement"):
                cur.execute(f"SELECT COUNT(*) AS c FROM {table} WHERE stock_code IN ({ph})", codes)
                out[table] = cur.fetchone()["c"]
            cur.execute("SELECT COUNT(*) AS c FROM news WHERE source='cls'")
            out["news_cls"] = cur.fetchone()["c"]
            cur.execute("SELECT COUNT(*) AS c FROM news WHERE stock_code IS NOT NULL")
            out["news_stock"] = cur.fetchone()["c"]
        return out
    finally:
        conn.close()


def run_once(codes: list[str]) -> dict:
    stock_info_fill.fill_base(codes)
    for code in codes:
        financial_fill.fill_statements(code)
        financial_fill.fill_indicators(code)
    end = date.today().isoformat()
    start = date(date.today().year - 2, 1, 1).isoformat()
    for code in codes:
        announcement_fill.run([code], start, end)
    news_fill.fill_cls()
    for code in codes:
        news_fill.fill_stock_news(code)
    return _counts(codes)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--codes", default="600519.SH,000001.SZ,300750.SZ")
    args = ap.parse_args()
    codes = [to_suffix(c) for c in args.codes.split(",") if c.strip()]

    print("== 第一遍 ==")
    c1 = run_once(codes)
    for k, v in c1.items():
        print(f"  {k}: {v}")

    print("== 第二遍（幂等验证）==")
    c2 = run_once(codes)
    for k, v in c2.items():
        print(f"  {k}: {v}")

    ok = all(c1[k] == c2[k] for k in c1)
    print("== 幂等校验 ==")
    if ok:
        print("  PASS：两遍各表行数一致")
    else:
        diff = {k: (c1[k], c2[k]) for k in c1 if c1[k] != c2[k]}
        print(f"  FAIL：差异 {diff}")


if __name__ == "__main__":
    main()
