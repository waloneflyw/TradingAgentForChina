# -*- coding: utf-8 -*-
"""金融助手对话端点 + 会话历史。

POST /api/chat                          —— 对话（续聊带 conversation_id，JSON 一次性返回）
POST /api/chat/stream                   —— 流式对话（SSE，子图「调用同事」事件冒泡）
GET  /api/conversations                 —— 会话列表
GET  /api/conversations/{id}/messages   —— 某会话消息
"""
from __future__ import annotations

import asyncio
import json
import threading

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessage, HumanMessage

from app.agents.assistant import create_assistant_agent, set_emit
from app.api import compliance, store
from app.api.deps import get_quick_llm
from app.api.schemas import ChatRequest

router = APIRouter(prefix="/api", tags=["chat"])

# 命中敏感词时，额外追加到 system 提示的一轮性合规兜底（④ 敏感兜底话术）
_COMPLIANCE_HINT = (
    "用户本次提问可能涉及违规内容（荐股承诺/代客理财/内幕消息/具体点位承诺），"
    "务必转回免责话术：不承诺收益、不预测点位、不构成投资建议。"
)


def _sse(event_type: str, data: dict) -> str:
    """把一条事件格式化成 SSE 帧（event: 类型 + data: JSON）。"""
    return f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _seed_from_db(conversation_id: int):
    """把 DB 里的历史消息还原成 LangChain 消息序列（只取 user/assistant 文本）。

    工具调用的中间消息不落库，续聊时 agent 会按需重新调工具，故只回填文本。
    """
    seed = []
    for r in store.get_messages(conversation_id):
        if r["role"] == "user":
            seed.append(HumanMessage(content=r["content"]))
        elif r["role"] == "assistant":
            seed.append(AIMessage(content=r["content"]))
    return seed


def _compliance_hint(message: str, conv_id) -> str:
    """命中敏感词则记日志 + 返回追加的合规提示，否则空串。"""
    hits = compliance.check_sensitive(message)
    if not hits:
        return ""
    compliance.log_sensitive(conv_id, message, hits)
    return _COMPLIANCE_HINT


@router.post("/chat")
def chat(req: ChatRequest):
    """对话：带 conversation_id 则续聊（回填历史），否则开新会话。落库 user + assistant。"""
    conv_id = req.conversation_id
    if conv_id is not None and not store.conversation_exists(conv_id):
        raise HTTPException(status_code=404, detail="会话不存在")

    seed = _seed_from_db(conv_id) if conv_id is not None else []
    hint = _compliance_hint(req.message, conv_id)

    # 跑 agent（闭包内部基于 seed 追加当前用户消息并执行工具循环）
    reply = create_assistant_agent(get_quick_llm(), history=seed, system_hint=hint)(req.message)

    if conv_id is None:
        conv_id = store.create_conversation(store.DEMO_USER_ID, title=req.message[:50])
    store.add_message(conv_id, "user", req.message)
    store.add_message(conv_id, "assistant", reply)

    return {"conversation_id": conv_id, "reply": reply}


@router.post("/chat/stream")
async def chat_stream(req: ChatRequest):
    """流式对话（SSE）。事件：meta → colleague/node/tool/report（子图冒泡）→ assistant → done/error。

    与 /api/chat 共享同一套落库逻辑；区别是当助手决定调 run_stock_analysis/run_screener 时，
    子图进度事件会冒泡到前端，实现「调用同事」的实时展示。
    """
    conv_id = req.conversation_id
    if conv_id is not None and not store.conversation_exists(conv_id):
        raise HTTPException(status_code=404, detail="会话不存在")

    seed = _seed_from_db(conv_id) if conv_id is not None else []
    hint = _compliance_hint(req.message, conv_id)

    loop = asyncio.get_running_loop()
    queue: asyncio.Queue = asyncio.Queue()

    def emit(ev: dict) -> None:
        loop.call_soon_threadsafe(queue.put_nowait, ev)

    def worker() -> None:
        final_conv_id = conv_id
        try:
            set_emit(emit)  # 让重工具冒泡「调用同事」事件（contextvar 在本线程可见）

            def on_delta(delta: str) -> None:
                emit({"type": "assistant_delta", "content": delta})

            reply = create_assistant_agent(
                get_quick_llm(), history=seed, system_hint=hint, on_delta=on_delta
            )(req.message)

            if final_conv_id is None:
                final_conv_id = store.create_conversation(store.DEMO_USER_ID, title=req.message[:50])
            store.add_message(final_conv_id, "user", req.message)
            store.add_message(final_conv_id, "assistant", reply)

            emit({"type": "assistant", "content": reply})
            emit({"type": "done", "conversation_id": final_conv_id})
        except Exception as e:  # 兜底：worker 任何未捕获异常也要推给前端
            emit({"type": "error", "message": f"服务异常：{e}"})

    threading.Thread(target=worker, daemon=True).start()

    async def event_stream():
        yield _sse("meta", {"conversation_id": conv_id})
        while True:
            ev = await queue.get()
            yield _sse(ev["type"], {k: v for k, v in ev.items() if k != "type"})
            if ev["type"] in ("done", "error"):
                break

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/conversations")
def list_conversations():
    return {"conversations": store.list_conversations(store.DEMO_USER_ID)}


@router.get("/conversations/{conversation_id}/messages")
def get_messages(conversation_id: int):
    if not store.conversation_exists(conversation_id):
        raise HTTPException(status_code=404, detail="会话不存在")
    return {"messages": store.get_messages(conversation_id)}
