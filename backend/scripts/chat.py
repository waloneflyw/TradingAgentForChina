# -*- coding: utf-8 -*-
"""阶段 3 · 金融助手对话 agent 验收入口。

用法（tradingagents 环境）：
    python scripts/chat.py

交互式对话循环。三类指令分别路由：
- 「分析贵州茅台」            → 拉起单股分析（11-agent，约 1-3 分钟）
- 「选新能源 PE<30 ROE>10」  → 拉起量化选股
- 其余（查行情/问概念/大盘） → 日常问答（search_stock / get_quote / get_market_overview）

输出应带合规免责话术。输入 quit 退出。
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

from app.config import Config  # noqa: E402
from app.llm_clients import create_llm_client  # noqa: E402
from app.agents.assistant import create_assistant_agent  # noqa: E402

BANNER = "=" * 68


def main() -> None:
    print(BANNER)
    print("A股智研助手 · 命令行对话")
    print("示例：「分析贵州茅台」/「选 新能源 PE<30 ROE>10」/「茅台现在多少钱」")
    print("输入 quit 退出")
    print(BANNER)

    llm = create_llm_client(
        provider=Config.LLM_PROVIDER,
        model=Config.QUICK_THINK_LLM,
        base_url=Config.BACKEND_URL,
    ).get_llm()
    chat = create_assistant_agent(llm)

    while True:
        try:
            msg = input("\n你 >>> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见。")
            break
        if not msg:
            continue
        if msg.lower() in ("quit", "exit", "q"):
            print("再见。")
            break

        print("\n助手 >>>")
        print(chat(msg))
        print("-" * 68)


if __name__ == "__main__":
    main()
