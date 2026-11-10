# -*- coding: utf-8 -*-
"""阶段 3 · 选股 agent 验收入口（量化初筛）。

用法（tradingagents 环境）：
    python scripts/screener.py --query "新能源、PE<30、ROE>10"
    python scripts/screener.py --query "医药生物 高增长 排除ST"
    python scripts/screener.py            # 无 --query 时进入交互追问循环

输出候选池总结（代码/名称/行业/ROE/PE/增速/关注度/换手等），并附风险提示。
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

from app.config import Config  # noqa: E402
from app.llm_clients import create_llm_client  # noqa: E402
from app.agents.screener import create_screener_agent  # noqa: E402

SECTION = "=" * 68


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="A股量化选股初筛")
    p.add_argument("--query", help="选股条件（自然语言），缺省进入交互模式")
    return p.parse_args()


def build_agent():
    llm = create_llm_client(
        provider=Config.LLM_PROVIDER,
        model=Config.QUICK_THINK_LLM,
        base_url=Config.BACKEND_URL,
    ).get_llm()
    return create_screener_agent(llm)


def main() -> None:
    args = parse_args()
    run = build_agent()

    if args.query:
        print(SECTION)
        print(f"选股条件：{args.query}")
        print(SECTION)
        print(run(args.query))
        return

    # 交互追问循环：保留多轮上下文，可对上一轮结果追加条件
    print("选股交互模式（输入 quit 退出）。例如：新能源、PE<30、ROE>10")
    context: list[str] = []
    while True:
        try:
            q = input("\n>>> 选股条件：").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not q:
            continue
        if q.lower() in ("quit", "exit", "q"):
            break
        context.append(q)
        # 把历史条件一起喂给 LLM，让它理解「在上一轮基础上继续筛」
        combined = "；".join(context)
        print("\n" + SECTION)
        print(run(combined))
        print(SECTION)


if __name__ == "__main__":
    main()
