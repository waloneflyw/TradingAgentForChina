# -*- coding: utf-8 -*-
"""LLM 客户端层：工厂 + OpenAI 兼容客户端（DeepSeek/Qwen）。

对外只暴露 create_llm_client，上层通过它拿 LangChain LLM 实例。
"""
from .factory import create_llm_client

__all__ = ["create_llm_client"]
