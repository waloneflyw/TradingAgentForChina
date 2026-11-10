# -*- coding: utf-8 -*-
"""阶段 3 · 单股分析验收入口。

用法（tradingagents 环境）：
    python scripts/analyze.py --code 600519.SH --date 2026-09-14
    python scripts/analyze.py --code 600519.SH --date 2026-09-14 --analysts market,fundamentals
    python scripts/analyze.py --code 600519.SH --date 2026-09-14 --debug

跑完 12 个节点（4 分析师 + 牛熊辩论 + 研究经理 + 交易员 + 三派风控 + 基金经理），
打印 4 份分析师报告 + 最终五档评级（买/增持/持有/减持/卖）。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # backend/

from app.graph import TradingAgentsGraph  # noqa: E402

SECTION = "=" * 68
SUB = "-" * 68


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="单股 11-agent 分析")
    p.add_argument("--code", required=True, help="股票代码（带后缀，如 600519.SH）")
    p.add_argument("--date", required=True, help="分析日期 yyyy-mm-dd")
    p.add_argument(
        "--analysts",
        default="market,fundamentals,news,social",
        help="逗号分隔的分析师子集：market/fundamentals/news/social",
    )
    p.add_argument("--debug", action="store_true", help="逐节点 stream + pretty_print")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    analysts = [a.strip() for a in args.analysts.split(",") if a.strip()]

    print(SECTION)
    print(f"单股分析：{args.code}  日期：{args.date}  分析师：{','.join(analysts)}")
    print(SECTION)

    graph = TradingAgentsGraph(selected_analysts=analysts, debug=args.debug)

    final_state, rating = graph.propagate(args.code, args.date)

    print("\n" + SUB)
    print("【技术面 Market】")
    print(SUB)
    print(final_state["market_report"] or "（未选中该分析师）")

    print("\n" + SUB)
    print("【基本面 Fundamentals】")
    print(SUB)
    print(final_state["fundamentals_report"] or "（未选中该分析师）")

    print("\n" + SUB)
    print("【新闻 News】")
    print(SUB)
    print(final_state["news_report"] or "（未选中该分析师）")

    print("\n" + SUB)
    print("【情绪 Social】")
    print(SUB)
    print(final_state["sentiment_report"] or "（未选中该分析师）")

    print("\n" + SECTION)
    print(f"最终评级：{rating}")
    print(SECTION)


if __name__ == "__main__":
    main()
