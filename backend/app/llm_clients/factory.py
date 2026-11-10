# -*- coding: utf-8 -*-
"""根据 provider 名创建 LLM 客户端的工厂。

【作用】把字符串 provider 映射到具体客户端类：
- openai / ollama / openrouter / deepseek / qwen / xai → 都走 OpenAI 兼容协议，
  统一用 OpenAIClient。
- anthropic / google 本版未移植（A股 MVP 只用 DeepSeek/Qwen），命中即报错提示。

上层（app/graph/trading_graph.py）只需 provider 名 + model 名即可拿到可用 LLM。
"""
from __future__ import annotations

from typing import Optional

from .base_client import BaseLLMClient
from .openai_client import OpenAIClient


def create_llm_client(
    provider: str,
    model: str,
    base_url: Optional[str] = None,
    **kwargs,
) -> BaseLLMClient:
    """为指定 provider 创建 LLM 客户端。

    Args:
        provider: 厂商名（openai / deepseek / qwen / ollama / openrouter / xai）
        model: 模型名（如 deepseek-v4-pro / deepseek-v4-flash）
        base_url: 可选，API 端点；缺省用厂商默认
        **kwargs: 额外参数（api_key / callbacks / timeout / deepseek_thinking 等）

    Returns:
        配置好的 BaseLLMClient 实例（get_llm() 拿 LangChain LLM）
    """
    provider_lower = provider.lower()

    if provider_lower in ("openai", "ollama", "openrouter", "deepseek", "qwen", "xai"):
        return OpenAIClient(model, base_url, provider=provider_lower, **kwargs)

    raise ValueError(f"Unsupported LLM provider: {provider}（A股 MVP 仅支持 OpenAI 兼容厂商）")
