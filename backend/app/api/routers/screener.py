# -*- coding: utf-8 -*-
"""选股端点：POST /api/screener。"""
from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import get_screener_agent
from app.api.schemas import ScreenerRequest

router = APIRouter(prefix="/api/screener", tags=["screener"])


@router.post("")
def run_screener(req: ScreenerRequest):
    """自然语言选股（同步端点，FastAPI 自动丢线程池，LLM 阻塞不卡事件循环）。"""
    result = get_screener_agent()(req.query)
    return {"query": req.query, "result": result}
