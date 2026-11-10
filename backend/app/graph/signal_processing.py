# -*- coding: utf-8 -*-
"""把基金经理的长文本提炼成「单个评级词」。

【作用】基金经理最终输出是一大段文字，不方便程序化使用（比如回测/前端展示）。
本文件用一次 LLM 调用，把结论强制规约成五档评级中的一个词：
  买 / 增持 / 持有 / 减持 / 卖
所以 graph.propagate() 返回的 rating 一定是这五个词之一。

【A股差异】评级词汇从参考项目的 BUY/OVERWEIGHT/HOLD/UNDERWEIGHT/SELL
改成中文五档，与 portfolio_manager 的输出和前端 §4.3 对齐。
"""
from __future__ import annotations

from typing import Any


class SignalProcessor:
    """Processes trading signals to extract actionable decisions."""

    def __init__(self, quick_thinking_llm: Any):
        """Initialize with an LLM for processing."""
        self.quick_thinking_llm = quick_thinking_llm

    def process_signal(self, full_signal: str) -> str:
        """Process a full trading signal to extract the core decision.

        Args:
            full_signal: Complete trading signal text

        Returns:
            Extracted rating (买, 增持, 持有, 减持, or 卖)
        """
        messages = [
            (
                "system",
                "You are an efficient assistant that extracts the trading decision from analyst reports. "
                "Extract the rating as exactly one of these five Chinese words: 买, 增持, 持有, 减持, 卖. "
                "Map any English equivalents (Buy/Overweight/Hold/Underweight/Sell) to the corresponding Chinese word. "
                "Output only the single rating word, nothing else.",
            ),
            ("human", full_signal),
        ]

        return self.quick_thinking_llm.invoke(messages).content
