# -*- coding: utf-8 -*-
"""FastAPI 应用工厂：CORS + 路由注册 + 启动时 seed demo 用户。"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import store
from app.api.routers import analysis, chat, market, screener


@asynccontextmanager
async def lifespan(app: FastAPI):
    # MVP 无鉴权，统一挂内置演示用户；启动时确保其存在（幂等）
    store.seed_demo_user()
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="A股智研 API", version="0.1.0", lifespan=lifespan)

    # CORS：阶段 5 前端 Vue3 独立端口联调用，先放开
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(analysis.router)
    app.include_router(screener.router)
    app.include_router(chat.router)
    app.include_router(market.router)

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    return app


app = create_app()
