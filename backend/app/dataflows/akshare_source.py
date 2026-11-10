# -*- coding: utf-8 -*-
"""akshare 统一封装：dir() 自检 + 限流 + 重试。

akshare 接口名随版本变（文档 §13.4），生产必须：
1. 启动/首次调用前 require() 自检关键接口名；
2. 每次调用走 call()，带重试 + 指数退避 + 简单限流（防东财反爬）。
"""
from __future__ import annotations

import os
import random
import threading
import time
from typing import Any, Callable

# akshare 内部用 tqdm 打印分页进度，管道脚本里太吵，统一静音。
os.environ.setdefault("TQDM_DISABLE", "1")

import akshare as ak  # noqa: E402

# 单线程/线程池管道里的简单限流：全局最小调用间隔（秒）
_MIN_INTERVAL = 0.25
_lock = threading.Lock()
_last_call = 0.0


def _throttle() -> None:
    global _last_call
    with _lock:
        now = time.monotonic()
        wait = _MIN_INTERVAL - (now - _last_call)
        if wait > 0:
            time.sleep(wait)
        _last_call = time.monotonic()


def call(fn: Callable, *args, retries: int = 4, backoff: float = 2.0, **kwargs) -> Any:
    """带重试的 akshare 调用。全部失败后抛 RuntimeError（附最后异常）。"""
    last: Exception | None = None
    for i in range(retries):
        _throttle()
        try:
            return fn(*args, **kwargs)
        except Exception as e:  # noqa: BLE001 — akshare 异常类型杂
            last = e
            if i < retries - 1:
                time.sleep(backoff * (2 ** i) + random.uniform(0, 0.5))
    name = getattr(fn, "__name__", str(fn))
    raise RuntimeError(f"akshare.{name} 失败 {retries} 次：{type(last).__name__}: {last}")


def require(*names: str) -> None:
    """启动自检：缺失接口立即报错（说明 akshare 版本变了）。"""
    missing = [n for n in names if not hasattr(ak, n)]
    if missing:
        raise RuntimeError(f"akshare {ak.__version__} 缺少接口：{missing}")
