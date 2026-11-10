# -*- coding: utf-8 -*-
"""LLM 客户端抽象基类 + 公共工具。

【作用】
- BaseLLMClient：规定每个厂商客户端必须实现 get_llm()（返回可用的 LangChain LLM），
  并提供 validate_model()（校验模型名，本版默认放行——模型名以 .env 为准）。
- normalize_content()：把不同厂商返回的 content 统一成纯字符串。
  OpenAI Responses API / 部分厂商会把 content 返回成
  [{type:'reasoning'},{type:'text', text:'...'}] 这类「分块列表」，
  而下游 agent 都期望 response.content 是字符串，这里负责抽文本块拼接。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional


def normalize_content(response):
    """把 LLM 返回的 content 归一化成字符串（抽取 text 块拼接，丢弃 reasoning/元数据块）。"""
    content = response.content
    if isinstance(content, list):
        texts = [
            item.get("text", "") if isinstance(item, dict) and item.get("type") == "text"
            else item if isinstance(item, str) else ""
            for item in content
        ]
        response.content = "\n".join(t for t in texts if t)
    return response


class BaseLLMClient(ABC):
    """LLM 客户端抽象基类。"""

    def __init__(self, model: str, base_url: Optional[str] = None, **kwargs):
        self.model = model
        self.base_url = base_url
        self.kwargs = kwargs

    def get_provider_name(self) -> str:
        """返回用于告警文案的 provider 名。"""
        provider = getattr(self, "provider", None)
        if provider:
            return str(provider)
        return self.__class__.__name__.removesuffix("Client").lower()

    def validate_model(self) -> bool:
        """校验模型名是否受支持。本版不做白名单校验（模型名以 .env 为准），默认放行。"""
        return True

    @abstractmethod
    def get_llm(self) -> Any:
        """返回配置好的 LangChain LLM 实例。"""
        raise NotImplementedError
