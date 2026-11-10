# -*- coding: utf-8 -*-
"""目标库通用 upsert（幂等落库）。

约定：
- 只写目标库 ashare_agent（Config.TARGET_DB），绝不碰源库 fastapi_db。
- 幂等靠表唯一键：INSERT ... ON DUPLICATE KEY UPDATE（重复跑不产生脏数据）。
- 各管道脚本只构造「业务列」的行 dict；id/create_time/update_time 由表默认值管，这里跳过。
"""
from __future__ import annotations

import json
import math
from datetime import date, datetime
from typing import Any, Sequence

import pymysql

from app.db.connection import target_conn

_META_SKIP = {"id", "create_time", "update_time"}


def _py(v: Any) -> Any:
    """Python 值 → MySQL 可写值（NaN/Inf → NULL，dict/list → JSON 字符串）。"""
    if v is None:
        return None
    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
        return None
    if isinstance(v, (dict, list)):
        return json.dumps(v, ensure_ascii=False)
    if isinstance(v, (date, datetime)):
        return v
    return v


def upsert(table: str, rows: Sequence[dict], keys: Sequence[str],
           conn: pymysql.connections.Connection | None = None) -> int:
    """按唯一键 upsert 一批行，返回写入行数。

    rows: 待写入行（列名 = 表列名）。keys: 唯一键列名（冲突时 UPDATE 其余列）。
    复用外部 conn 可减少连接开销（批量分块写时传入）。
    """
    if not rows:
        return 0
    cols = [c for c in rows[0].keys() if c not in _META_SKIP]
    keys = [k for k in keys if k in cols]
    update_cols = [c for c in cols if c not in keys]
    if not update_cols:
        update_cols = [cols[0]]  # 纯键表：退化为原地更新（无实际变化）

    col_sql = ", ".join(f"`{c}`" for c in cols)
    ph = ", ".join(["%s"] * len(cols))
    upd_sql = ", ".join(f"`{c}`=VALUES(`{c}`)" for c in update_cols)
    sql = (f"INSERT INTO `{table}` ({col_sql}) VALUES ({ph}) "
           f"ON DUPLICATE KEY UPDATE {upd_sql}")

    owns = conn is None
    if owns:
        conn = target_conn()
    try:
        params = [[_py(r.get(c)) for c in cols] for r in rows]
        with conn.cursor() as cur:
            cur.executemany(sql, params)
        conn.commit()
        return len(rows)
    finally:
        if owns:
            conn.close()
