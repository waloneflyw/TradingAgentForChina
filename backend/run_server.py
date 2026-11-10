# -*- coding: utf-8 -*-
"""阶段 4 服务启动入口（tradingagents 环境）。

用法：
    python run_server.py                 # 默认 0.0.0.0:8000
    python run_server.py --port 8080

注意：MVP 无登录鉴权，所有数据挂在内置 demo 用户（user.id=1）下，
仅用于阶段 4/5 联调；阶段 5 前端登录做完前不要对公网开放。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# 保证无论从哪个目录启动，都能 import 到 app 包
sys.path.insert(0, str(Path(__file__).resolve().parent))  # backend/

import uvicorn  # noqa: E402

from app.config import Config  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="A股智研 API 服务")
    parser.add_argument("--host", default=Config.API_HOST)
    parser.add_argument("--port", type=int, default=Config.API_PORT)
    args = parser.parse_args()

    uvicorn.run("app.api.main:app", host=args.host, port=args.port, reload=False)


if __name__ == "__main__":
    main()
