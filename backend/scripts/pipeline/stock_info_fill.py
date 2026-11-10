# -*- coding: utf-8 -*-
"""stock_info 填充：一次性拷 fastapi_db.stocks + 增补 list_date/is_st/申万行业。

用法（tradingagents 环境）：
    python scripts/pipeline/stock_info_fill.py                     # 全市场基础信息（无 API，快）
    python scripts/pipeline/stock_info_fill.py --sw                # 追加申万行业（官方 API 一次拉全，缓存 .sw_cache.json）
    python scripts/pipeline/stock_info_fill.py --codes 600519.SH   # 只填指定股（+ --sw 时只更新这些股）
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # backend/

from app.db.connection import source_conn, target_conn  # noqa: E402
from app.dataflows.db_writer import upsert  # noqa: E402

CACHE = Path(__file__).resolve().parent / ".sw_cache.json"


def _is_st(name: str) -> int:
    n = (name or "").strip().upper()
    return 1 if n.startswith(("*ST", "ST", "＊ST")) else 0


def _parse_codes(raw: str | None) -> list[str] | None:
    if not raw:
        return None
    from app.dataflows.symbols import to_suffix
    return [to_suffix(c) for c in raw.split(",") if c.strip()]


def fill_base(codes: list[str] | None) -> int:
    """拷 stocks + list_date(min trade_date) + is_st → stock_info。返回写入行数。"""
    src = source_conn()
    tgt = target_conn()
    try:
        # 1) 源 stocks（只读）
        sql = "SELECT code, name, market, pinyin, status FROM stocks"
        if codes:
            ph = ",".join(["%s"] * len(codes))
            sql += f" WHERE code IN ({ph})"
        with src.cursor() as cur:
            cur.execute(sql, codes or ())
            stocks = cur.fetchall()

        # 2) list_date：用自建 daily_bar 的 MIN(trade_date)（比外部接口稳、准）
        with tgt.cursor() as cur:
            cur.execute("SELECT stock_code, MIN(trade_date) AS list_date "
                        "FROM daily_bar GROUP BY stock_code")
            list_dates = {r["stock_code"]: r["list_date"] for r in cur.fetchall()}

        # 3) 组装行
        rows = []
        for s in stocks:
            code = s["code"]
            rows.append({
                "stock_code": code,
                "name": s["name"],
                "pinyin": s["pinyin"] or "",
                "market": s["market"] or "",
                "status": s["status"] or "LISTED",
                "list_date": list_dates.get(code),
                "is_st": _is_st(s["name"]),
            })
        n = upsert("stock_info", rows, ["stock_code"], conn=tgt)
        print(f"[base] stocks={len(stocks)} 落库={n}")
        return n
    finally:
        src.close()
        tgt.close()


def fill_sw(codes: list[str] | None, max_passes: int = 3) -> None:
    """申万行业 enrichment：官方 API 构建反向索引 → UPDATE stock_info。

    数据源已从 legulegu（易限流）切到申万宏源官网 API：一次性拉全 31 一级 + 124 二级
    指数成分，无需按行业逐个抓 335 次。结果落 .sw_cache.json；整趟失败则重试 max_passes 次。
    """
    from app.dataflows import sw_industry

    merged: dict[str, tuple[str, str]] = {}
    if CACHE.exists():
        merged = {k: tuple(v) for k, v in json.loads(CACHE.read_text(encoding="utf-8")).items()}
        print(f"[sw] 旧缓存 {len(merged)} 只，将与新结果合并…")

    idx: dict[str, tuple[str, str]] = {}
    for p in range(1, max_passes + 1):
        try:
            idx = sw_industry.build_stock_industry(
                progress=lambda m: print("\r[sw]", m, end="", flush=True)
            )
            print()
            break
        except Exception as e:  # noqa: BLE001 — 网络异常类型杂，整趟重试即可
            print(f"\n[sw] 第 {p} 趟失败：{type(e).__name__}: {e}")
            if p < max_passes:
                time.sleep(5)
    else:
        raise RuntimeError(f"[sw] 跑满 {max_passes} 趟仍失败，稍后重跑（缓存会续跑）。")

    merged = {**merged, **idx}  # 新结果覆盖旧值，旧缓存已命中的股不丢
    CACHE.write_text(json.dumps(merged, ensure_ascii=False), encoding="utf-8")
    print(f"[sw] 本趟构建 {len(idx)} 只；合并后缓存 {len(merged)} 只")

    tgt = target_conn()
    try:
        items = merged.items() if not codes else [(c, merged[c]) for c in codes if c in merged]
        with tgt.cursor() as cur:
            for code, (l1, l2) in items:
                cur.execute("UPDATE stock_info SET industry_sw_l1=%s, industry_sw_l2=%s "
                            "WHERE stock_code=%s", (l1 or None, l2 or None, code))
        tgt.commit()
        print(f"[sw] 更新 {len(items)} 只；命中不足的股保持 NULL")
    finally:
        tgt.close()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--codes", help="逗号分隔代码，默认全市场")
    ap.add_argument("--sw", action="store_true", help="追加申万行业 enrichment")
    ap.add_argument("--sw-only", action="store_true", help="只跑申万行业，不拷 stocks")
    args = ap.parse_args()
    codes = _parse_codes(args.codes)

    if not args.sw_only:
        fill_base(codes)
    if args.sw or args.sw_only:
        fill_sw(codes)


if __name__ == "__main__":
    main()
