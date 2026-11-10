"""MySQL 连接工具（pymysql，阶段 0 一次性脚本用）。

约定：
- fastapi_db 只读（source），严禁任何写操作；
- ashare_agent 可读写（target），所有新数据写入这里。
"""
from __future__ import annotations

import pymysql

from app.config import Config


def _connect(db: str | None) -> pymysql.connections.Connection:
    kwargs: dict = dict(
        host=Config.DB_HOST,
        port=Config.DB_PORT,
        user=Config.DB_USER,
        password=Config.DB_PASSWORD,
        charset=Config.DB_CHARSET,
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False,
        # 对应 mysql CLI 的 --ssl-mode=DISABLED：pymysql 默认即不启用 SSL。
    )
    if db:
        kwargs["database"] = db
    return pymysql.connect(**kwargs)


def server_conn() -> pymysql.connections.Connection:
    """无库连接（用于 CREATE DATABASE / USE 等 DDL）。"""
    return _connect(None)


def source_conn() -> pymysql.connections.Connection:
    """只读源库（fastapi_db）连接。"""
    return _connect(Config.SOURCE_DB)


def target_conn() -> pymysql.connections.Connection:
    """目标库（ashare_agent）连接。"""
    return _connect(Config.TARGET_DB)


# 供一次性脚本直接引用目标库名
TARGET_DB = Config.TARGET_DB
