# -*- coding: utf-8 -*-
"""财务管道：三大报表竖表 + 财务指标（akshare 东财）。

symbol 格式：三大报表用前缀（SH600519），财务指标用后缀（600519.SH），存库统一后缀。

用法（tradingagents 环境）：
    python scripts/pipeline/financial_fill.py --codes 600519.SH,000001.SZ      # 指定股
    python scripts/pipeline/financial_fill.py --all --indicators-only          # 全市场财务指标（快，~20 分钟）
    python scripts/pipeline/financial_fill.py --all --statements-only          # 全市场三大报表（慢，~24 小时，断点续跑）
    python scripts/pipeline/financial_fill.py --all                            # 两者全量
    python scripts/pipeline/financial_fill.py --all --limit 100               # 只跑前 100 只（测试）

断点续跑：进度写 .fin_cache.json（{code: {"ind": N, "stmt": N}}，键存在即算完成），
失败股不写键、下次重跑自动补。指标行数少，建议先 --indicators-only 解锁选股，再错峰跑报表。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime
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
from app.dataflows.financial_map import (  # noqa: E402
    INDICATOR_COL_MAP, STATEMENT_MAP, STATEMENT_META_COLS,
)
from app.dataflows.symbols import to_prefix, to_suffix  # noqa: E402
from app.db.connection import target_conn  # noqa: E402

# 三大报表类型 → akshare 接口
_SHEET_FN = {
    "balance": ak.stock_balance_sheet_by_report_em,
    "income": ak.stock_profit_sheet_by_report_em,
    "cashflow": ak.stock_cash_flow_sheet_by_report_em,
}

# 断点续跑缓存（与 .sw_cache.json 同目录，思路一致：增量续跑）
CACHE = Path(__file__).resolve().parent / ".fin_cache.json"

# 每 N 只刷新一次缓存（失败/中断最多重跑 N 只）
_FLUSH_EVERY = 20


def _to_date(v) -> str | None:
    """'2026-06-30 00:00:00' / datetime / date → 'YYYY-MM-DD'。"""
    if v is None:
        return None
    if isinstance(v, datetime):
        return v.date().isoformat()
    if isinstance(v, str):
        return v[:10]
    return None


def _num(v):
    """清洗数值：None/NaN/Inf/非数值文本（如审计意见）→ None；其余统一 Decimal 保精度。"""
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


def fill_statements(code: str, conn=None) -> int:
    """某股三大报表 → 竖表。返回写入行数。"""
    prefix = to_prefix(code)
    suffix = to_suffix(code)
    rows = []
    for rtype, fn in _SHEET_FN.items():
        df = src.call(fn, symbol=prefix)
        item_cols = [c for c in df.columns if c not in STATEMENT_META_COLS]
        cn_map = STATEMENT_MAP[rtype]
        for _, row in df.iterrows():
            rd = _to_date(row.get("REPORT_DATE"))
            if not rd:
                continue
            for col in item_cols:
                val = _num(row.get(col))
                if val is None:
                    continue
                rows.append({
                    "stock_code": suffix,
                    "report_date": rd,
                    "report_type": rtype,
                    "item_name": cn_map.get(col, col),
                    "item_value": val,
                })
    return upsert("financial_statement", rows, ["stock_code", "report_date", "report_type", "item_name"], conn=conn)


def fill_indicators(code: str, conn=None) -> int:
    """某股财务指标 → financial_indicator（报告期质量/成长指标）。"""
    suffix = to_suffix(code)
    df = src.call(ak.stock_financial_analysis_indicator_em, symbol=suffix, indicator="按报告期")
    rows = []
    for _, row in df.iterrows():
        rd = _to_date(row.get("REPORT_DATE"))
        if not rd:
            continue
        rec = {"stock_code": suffix, "report_date": rd}
        for tbl_col, src_col in INDICATOR_COL_MAP.items():
            rec[tbl_col] = _num(row.get(src_col))
        rows.append(rec)
    return upsert("financial_indicator", rows, ["stock_code", "report_date"], conn=conn)


def run(codes: list[str]) -> None:
    src.require("stock_balance_sheet_by_report_em", "stock_profit_sheet_by_report_em",
                "stock_cash_flow_sheet_by_report_em", "stock_financial_analysis_indicator_em")
    conn = target_conn()
    try:
        for code in codes:
            n_stmt = fill_statements(code, conn=conn)
            n_ind = fill_indicators(code, conn=conn)
            print(f"{code}: 报表竖表 {n_stmt} 行，指标 {n_ind} 行")
    finally:
        conn.close()


# ---- 全市场断点续跑 ----


def _load_cache() -> dict:
    if CACHE.exists():
        try:
            return json.loads(CACHE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            print(f"[warn] 缓存 {CACHE.name} 损坏，忽略重跑")
    return {}


def _save_cache(cache: dict) -> None:
    CACHE.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")


def _pending_codes(indicators: bool, statements: bool, cache: dict) -> list[str]:
    """stock_info 全代码里，待回填（请求的部分还没在缓存里标记完成）的那些。"""
    conn = target_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT stock_code FROM stock_info ORDER BY stock_code")
            codes = [r["stock_code"] for r in cur.fetchall()]
    finally:
        conn.close()

    todo = []
    for c in codes:
        done = cache.get(c, {})
        if (indicators and "ind" not in done) or (statements and "stmt" not in done):
            todo.append(c)
    return todo


def run_all(indicators: bool, statements: bool, limit: int | None = None, resume: bool = True) -> None:
    """遍历 stock_info 全代码回填，断点续跑（.fin_cache.json 记录每只完成情况）。

    Args:
        indicators: 回填财务指标（快）。
        statements: 回填三大报表（慢，东财分页 ~16s/股）。
        limit: 只处理前 N 只待办（测试用）。
        resume: False 则忽略缓存、从零重跑（不覆盖已完成，仅重新过一遍全部）。
    """
    src.require("stock_balance_sheet_by_report_em", "stock_profit_sheet_by_report_em",
                "stock_cash_flow_sheet_by_report_em", "stock_financial_analysis_indicator_em")

    cache = _load_cache() if resume else {}
    todo = _pending_codes(indicators, statements, cache)
    if limit:
        todo = todo[:limit]
    total = len(todo)
    parts = []
    if indicators:
        parts.append("指标")
    if statements:
        parts.append("报表")
    print(f"[全市场] 待回填 {total} 只（{' + '.join(parts)}），缓存已含 {len(cache)} 只。")
    if total == 0:
        print("[全市场] 无待办，已全部完成。")
        return

    conn = target_conn()
    t0 = time.time()
    n_ok = 0
    n_fail = 0
    try:
        for i, code in enumerate(todo, 1):
            done = cache.setdefault(code, {})
            try:
                if indicators and "ind" not in done:
                    done["ind"] = fill_indicators(code, conn=conn)
                if statements and "stmt" not in done:
                    done["stmt"] = fill_statements(code, conn=conn)
                n_ok += 1
            except Exception as e:  # noqa: BLE001 — 单只失败不中断全量，留待下次续跑
                n_fail += 1
                print(f"[失败] {code}: {type(e).__name__}: {str(e)[:120]}")

            if i % _FLUSH_EVERY == 0:
                _save_cache(cache)

            if i % 50 == 0 or i == total:
                rate = (time.time() - t0) / i
                eta = rate * (total - i)
                print(f"[进度] {i}/{total} 成功 {n_ok} 失败 {n_fail} "
                      f"均速 {rate:.2f}s/股 ETA {eta/60:.0f} 分钟")
    except KeyboardInterrupt:
        print("\n[中断] 已保存缓存，下次续跑。")
        raise
    finally:
        _save_cache(cache)
        conn.close()

    print(f"[全市场] 完成：成功 {n_ok}，失败 {n_fail}（失败股下次续跑自动补）。")


def main() -> None:
    ap = argparse.ArgumentParser(description="财务数据回填（指标/三大报表，支持全市场断点续跑）")
    ap.add_argument("--codes", help="逗号分隔代码（后缀/裸/前缀均可），与 --all 二选一")
    ap.add_argument("--all", action="store_true", help="遍历 stock_info 全市场回填")
    ap.add_argument("--indicators-only", action="store_true", help="只回填财务指标（选股初筛因子）")
    ap.add_argument("--statements-only", action="store_true", help="只回填三大报表竖表")
    ap.add_argument("--limit", type=int, default=None, help="只处理前 N 只待办（测试用）")
    ap.add_argument("--no-resume", action="store_true", help="忽略缓存从头跑（不删已落库数据）")
    args = ap.parse_args()

    if args.all:
        indicators = not args.statements_only
        statements = not args.indicators_only
        run_all(indicators, statements, limit=args.limit, resume=not args.no_resume)
    else:
        if not args.codes:
            ap.error("需要 --codes 或 --all")
        codes = [to_suffix(c) for c in args.codes.split(",") if c.strip()]
        run(codes)


if __name__ == "__main__":
    main()
