# -*- coding: utf-8 -*-
"""公告管道：巨潮 cninfo 直连 → announcement 表。

用法（tradingagents 环境）：
    python scripts/pipeline/announcement_fill.py --codes 600519.SH,000001.SZ --start 2024-01-01
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

from app.dataflows import cninfo  # noqa: E402
from app.dataflows.db_writer import upsert  # noqa: E402
from app.dataflows.symbols import to_suffix  # noqa: E402
from app.db.connection import target_conn  # noqa: E402


def run(codes: list[str], start: str, end: str) -> None:
    conn = target_conn()
    try:
        for code in codes:
            anns = cninfo.fetch_announcements(code, start, end)
            # announcement 表只需列表字段；正文按需解析（可空）
            rows = [{
                "stock_code": a["stock_code"],
                "title": a["title"],
                "url": a["url"],
                "announce_time": a["announce_time"],
                "category": a["category"],
            } for a in anns if a["announce_time"]]
            n = upsert("announcement", rows, ["url"], conn=conn)
            print(f"{code}: {len(anns)} 条公告，落库 {n}")
    finally:
        conn.close()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--codes", required=True, help="逗号分隔代码")
    ap.add_argument("--start", default=(date.today().replace(year=date.today().year - 2)).isoformat(),
                    help="起始日 YYYY-MM-DD，默认两年前")
    ap.add_argument("--end", default=date.today().isoformat(), help="截止日 YYYY-MM-DD，默认今天")
    args = ap.parse_args()
    codes = [to_suffix(c) for c in args.codes.split(",") if c.strip()]
    run(codes, args.start, args.end)


if __name__ == "__main__":
    main()
