# -*- coding: utf-8 -*-
"""阶段 4 请求模型（Pydantic）。"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class AnalysisRequest(BaseModel):
    """单股分析请求。date 缺省用今天。"""

    code: str  # 股票代码，如 600519.SH / 600519
    date: Optional[str] = None  # 分析基准日期 yyyy-mm-dd


class ScreenerRequest(BaseModel):
    """选股请求。"""

    query: str  # 自然语言条件，如 新能源、PE<30、ROE>10


class ChatRequest(BaseModel):
    """对话请求。首次对话不带 conversation_id；续聊带上以保留上下文。"""

    message: str
    conversation_id: Optional[int] = None
