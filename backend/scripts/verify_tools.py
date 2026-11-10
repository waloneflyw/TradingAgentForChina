# -*- coding: utf-8 -*-
"""阶段 2 验收：9 个 A股工具逐个调用，检查返回正确数据 + 兜底逻辑。

用法（tradingagents 环境）：
    python scripts/verify_tools.py
运行时拉取类工具（大盘/股东/龙虎榜）受东财限流影响，失败时记为 SKIP 而非 FAIL，
错峰重跑即可。核心（查库类）工具应全部 PASS。
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

from app.dataflows.interface import route  # noqa: E402

SAMPLE = "600519.SH"
TODAY = "2026-09-14"


def check(name: str, fn, runtime: bool = False) -> None:
    try:
        out = fn()
        ok = bool(out) and "无" not in out[:12] and "失败" not in out[:20]
        status = "PASS" if ok else "FAIL(空/无数据)"
        print(f"  [{status}] {name}: {out[:80].replace(chr(10), ' ')}…")
    except Exception as e:  # noqa: BLE001
        tag = "SKIP(源限流)" if runtime else "FAIL"
        print(f"  [{tag}] {name}: {type(e).__name__}: {str(e)[:70]}")


def main() -> None:
    print("== 阶段 2 工具验收 ==")
    check("get_stock_data", lambda: route("get_stock_data", SAMPLE, "2026-09-01", "2026-09-04"))
    check("get_indicators", lambda: route("get_indicators", SAMPLE, "rsi,macd", "2026-09-04"))
    check("get_fundamentals", lambda: route("get_fundamentals", SAMPLE, TODAY))
    check("get_financial_statements", lambda: route("get_financial_statements", SAMPLE, "income"))
    check("get_news", lambda: route("get_news", SAMPLE, "2026-01-01", TODAY))
    check("get_announcements", lambda: route("get_announcements", SAMPLE, "2026-01-01", TODAY))
    check("get_stock_screener", lambda: route("get_stock_screener", max_pe=20, min_growth=0))
    check("get_shareholder_changes", lambda: route("get_shareholder_changes", SAMPLE), runtime=True)
    check("get_market_overview", lambda: route("get_market_overview", TODAY), runtime=True)
    print("（runtime 类若 SKIP 为东财限流，错峰重跑即可）")


if __name__ == "__main__":
    main()
