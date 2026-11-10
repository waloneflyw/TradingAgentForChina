# -*- coding: utf-8 -*-
"""阶段 4 依赖单例：进程内复用 11-agent 图 / 选股 agent / 快速 LLM。

【为什么单例】TradingAgentsGraph 构造时会创建 2 个 LLM 客户端 + 编译整张图，
开销不小；FastAPI 多请求并发下应复用同一份，而非每请求重建（assistant.py 同理）。
"""
from __future__ import annotations

from app.config import Config
from app.llm_clients import create_llm_client

_graph = None
_screener_agent = None
_quick_llm = None


def get_graph():
    """懒加载 11-agent 分析图单例。"""
    global _graph
    if _graph is None:
        from app.graph import TradingAgentsGraph
        _graph = TradingAgentsGraph()
    return _graph


def get_quick_llm():
    """懒加载快速 LLM（选股 / 对话 / 信号提炼共用）。"""
    global _quick_llm
    if _quick_llm is None:
        _quick_llm = create_llm_client(
            provider=Config.LLM_PROVIDER,
            model=Config.QUICK_THINK_LLM,
            base_url=Config.BACKEND_URL,
        ).get_llm()
    return _quick_llm


def get_screener_agent():
    """懒加载选股 agent 单例。"""
    global _screener_agent
    if _screener_agent is None:
        from app.agents.screener import create_screener_agent
        _screener_agent = create_screener_agent(get_quick_llm())
    return _screener_agent
