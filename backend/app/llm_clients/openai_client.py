# -*- coding: utf-8 -*-
"""OpenAI 及「OpenAI 兼容协议」厂商的客户端（DeepSeek/Qwen 都走这条路）。

【作用】不只服务原生 OpenAI，还统一承接所有 OpenAI 兼容厂商：
deepseek / qwen（通义千问）/ openrouter / ollama / xai。
它们都用 /v1/chat/completions 风格接口，所以复用 langchain_openai.ChatOpenAI。

【关键点】
- DeepSeek V4 默认开思考模式，配合工具调用会因 reasoning_content 报 400，
  所以默认显式关闭思考（除非传 deepseek_thinking=True）。
- NormalizedChatOpenAI 重写 invoke()，把分块 content 归一化成字符串（见 base_client）。
"""
from __future__ import annotations

import os
from typing import Any, Dict, Optional

from langchain_openai import ChatOpenAI

from .base_client import BaseLLMClient, normalize_content


class NormalizedChatOpenAI(ChatOpenAI):
    """ChatOpenAI with normalized content output（content 统一成字符串）。"""

    def invoke(self, input, config=None, **kwargs):
        return normalize_content(super().invoke(input, config, **kwargs))


# 允许从上层 kwargs 透传给 ChatOpenAI 的参数
_PASSTHROUGH_KWARGS = (
    "timeout", "max_retries", "reasoning_effort",
    "api_key", "callbacks", "http_client", "http_async_client",
)

# 各 OpenAI 兼容厂商的默认 base_url + API key 环境变量名
_PROVIDER_CONFIG = {
    "xai": ("https://api.x.ai/v1", "XAI_API_KEY"),
    "openrouter": ("https://openrouter.ai/api/v1", "OPENROUTER_API_KEY"),
    "ollama": ("http://localhost:11434/v1", None),
    "deepseek": ("https://api.deepseek.com/v1", "DEEPSEEK_API_KEY"),
    "qwen": ("https://dashscope.aliyuncs.com/compatible-mode/v1", "DASHSCOPE_API_KEY"),
}


class OpenAIClient(BaseLLMClient):
    """OpenAI 及兼容厂商客户端。"""

    def __init__(self, model: str, base_url: Optional[str] = None, provider: str = "openai", **kwargs):
        super().__init__(model, base_url, **kwargs)
        self.provider = provider.lower()

    def get_llm(self) -> Any:
        """返回配置好的 ChatOpenAI 实例。"""
        llm_kwargs: Dict[str, Any] = {"model": self.model}

        # 厂商默认 base_url + auth；显式传入的 base_url 优先
        if self.provider in _PROVIDER_CONFIG:
            default_url, api_key_env = _PROVIDER_CONFIG[self.provider]
            llm_kwargs["base_url"] = self.base_url or default_url
            if api_key_env:
                api_key = os.environ.get(api_key_env)
                if api_key:
                    llm_kwargs["api_key"] = api_key
            else:
                llm_kwargs["api_key"] = "ollama"
        elif self.base_url:
            llm_kwargs["base_url"] = self.base_url

        # 透传上层 kwargs
        for key in _PASSTHROUGH_KWARGS:
            if key in self.kwargs:
                llm_kwargs[key] = self.kwargs[key]

        # 原生 OpenAI 用 Responses API；第三方兼容厂商走 Chat Completions
        if self.provider == "openai":
            llm_kwargs["use_responses_api"] = True

        # DeepSeek 默认关思考模式，避免工具调用 400
        if self.provider == "deepseek" and not self.kwargs.get("deepseek_thinking", False):
            llm_kwargs["extra_body"] = {"thinking": {"type": "disabled"}}

        return NormalizedChatOpenAI(**llm_kwargs)
