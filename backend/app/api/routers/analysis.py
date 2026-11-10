# -*- coding: utf-8 -*-
"""单股分析端点。

POST /api/analysis       —— SSE 流式（meta → node/tool/report → done/error）
GET  /api/analysis/{task_id} —— 读历史报告全文（断线重连 / 助手 get_report）
"""
from __future__ import annotations

import asyncio
import json
import threading
from datetime import date
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.api import store
from app.api.analysis_service import run_analysis_sync
from app.api.schemas import AnalysisRequest

router = APIRouter(prefix="/api/analysis", tags=["analysis"])


def _sse(event_type: str, data: dict) -> str:
    """把一条事件格式化成 SSE 帧（event: 类型 + data: JSON）。"""
    return f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("")
async def run_analysis(req: AnalysisRequest):
    """启动一次单股分析，返回 SSE 流。断开也不影响后台继续跑完并落库。"""
    task_id = uuid4().hex[:16]
    analysis_date = req.date or date.today().isoformat()

    loop = asyncio.get_running_loop()
    queue: asyncio.Queue = asyncio.Queue()

    def emit(ev: dict) -> None:
        loop.call_soon_threadsafe(queue.put_nowait, ev)

    def worker() -> None:
        try:
            result = run_analysis_sync(req.code, analysis_date, task_id, emit)
            emit({"type": "done", "task_id": task_id, **result})
        except Exception as e:  # 兜底：worker 任何未捕获异常也要推给前端
            emit({"type": "error", "message": f"服务异常：{e}"})

    threading.Thread(target=worker, daemon=True).start()

    async def event_stream():
        yield _sse("meta", {"task_id": task_id, "code": req.code, "date": analysis_date})
        while True:
            ev = await queue.get()
            yield _sse(ev["type"], {k: v for k, v in ev.items() if k != "type"})
            if ev["type"] in ("done", "error"):
                break

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/{task_id}")
def get_report(task_id: str):
    """读历史报告全文。"""
    report = store.get_report(task_id)
    if not report:
        raise HTTPException(status_code=404, detail="报告不存在")
    return report
