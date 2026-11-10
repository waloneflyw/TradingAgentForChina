# -*- coding: utf-8 -*-
"""阶段 4 落库层：报告 / 过程 trace / 会话 / 消息 的读写封装。

【约定】所有写操作只走 target_conn（ashare_agent）；fastapi_db 只读、严禁写。
连接用完即关（短连接 + pymysql 同步），配合 worker 线程使用（不在事件循环里跑）。

【MVP】无真实鉴权，所有接口统一挂在内置演示用户（user.id=1）下，阶段 5 登录后再换。
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from app.db.connection import target_conn

DEMO_USER_ID = 1
DEMO_USERNAME = "demo"


def seed_demo_user() -> None:
    """启动时确保演示用户存在（幂等，重复调用不报错）。"""
    conn = target_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT IGNORE INTO user (id, username, password_hash, nickname) "
                "VALUES (%s, %s, %s, %s)",
                (DEMO_USER_ID, DEMO_USERNAME, "!no-auth", "演示用户"),
            )
        conn.commit()
    finally:
        conn.close()


def lookup_stock(code: str):
    """查 stock_info 拿股票名称 + 申万一级行业，用作报告检索元数据。"""
    conn = target_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT name, industry_sw_l1 FROM stock_info WHERE stock_code=%s LIMIT 1",
                (code,),
            )
            row = cur.fetchone()
    finally:
        conn.close()
    if row:
        return row["name"], row["industry_sw_l1"]
    return None, None


# ---------------- 分析报告 / trace ----------------

def save_report(
    task_id: str,
    code: str,
    name: Optional[str],
    industry: Optional[str],
    rating: str,
    analysis_date: str,
    summary: str,
    report_json: Dict[str, Any],
) -> None:
    """写入一份分析报告（analysis_report）。report_json 序列化成 JSON 列。"""
    conn = target_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO analysis_report "
                "(task_id, user_id, stock_code, stock_name, industry, rating, "
                " analysis_date, summary, report_json) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (
                    task_id,
                    DEMO_USER_ID,
                    code,
                    name,
                    industry,
                    rating,
                    analysis_date,
                    summary,
                    json.dumps(report_json, ensure_ascii=False),
                ),
            )
        conn.commit()
    finally:
        conn.close()


def save_trace(
    task_id: str,
    seq: int,
    node_name: Optional[str],
    event_type: str,
    summary: Optional[Dict[str, Any]] = None,
) -> None:
    """写入一条过程事件（analysis_trace），(task_id, seq) 唯一，按序回放用。"""
    conn = target_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO analysis_trace (task_id, seq, node_name, event_type, summary) "
                "VALUES (%s, %s, %s, %s, %s)",
                (
                    task_id,
                    seq,
                    node_name,
                    event_type,
                    json.dumps(summary, ensure_ascii=False) if summary is not None else None,
                ),
            )
        conn.commit()
    finally:
        conn.close()


def get_report(task_id: str) -> Optional[Dict[str, Any]]:
    """读历史报告全文；不存在返回 None。report_json 反序列化成 dict。"""
    conn = target_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT task_id, stock_code, stock_name, industry, rating, "
                " analysis_date, summary, report_json, create_time "
                "FROM analysis_report WHERE task_id=%s",
                (task_id,),
            )
            row = cur.fetchone()
    finally:
        conn.close()

    if not row:
        return None

    rj = row.get("report_json")
    if isinstance(rj, str):
        try:
            row["report_json"] = json.loads(rj)
        except json.JSONDecodeError:
            pass
    return row


def search_reports(
    stock_code: Optional[str] = None,
    industry: Optional[str] = None,
    rating: Optional[str] = None,
    limit: int = 10,
) -> List[Dict[str, Any]]:
    """按条件检索历史报告（全局知识库），只返回元数据 + 结论摘要，不返全文。

    stock_code 支持后缀代码精确匹配；industry 走 LIKE 模糊（申万一级名）。
    """
    where = []
    params: list = []
    if stock_code:
        where.append("stock_code = %s")
        params.append(stock_code)
    if industry:
        where.append("industry LIKE %s")
        params.append(f"%{industry}%")
    if rating:
        where.append("rating = %s")
        params.append(rating)

    where_sql = ("WHERE " + " AND ".join(where)) if where else ""
    sql = (
        "SELECT task_id, stock_code, stock_name, industry, rating, analysis_date, summary, create_time "
        f"FROM analysis_report {where_sql} ORDER BY create_time DESC LIMIT %s"
    )
    params.append(limit)

    conn = target_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall()
    finally:
        conn.close()


# ---------------- 会话 / 消息 ----------------

def create_conversation(user_id: int, title: Optional[str] = None) -> int:
    """新建会话，返回会话 id。"""
    conn = target_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO conversation (user_id, title) VALUES (%s, %s)",
                (user_id, title),
            )
            new_id = cur.lastrowid
        conn.commit()
    finally:
        conn.close()
    return new_id


def conversation_exists(conversation_id: int) -> bool:
    conn = target_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM conversation WHERE id=%s", (conversation_id,))
            return cur.fetchone() is not None
    finally:
        conn.close()


def add_message(
    conversation_id: int,
    role: str,
    content: str,
    msg_type: str = "text",
    task_id: Optional[str] = None,
    report_id: Optional[int] = None,
) -> None:
    """追加一条消息（user/assistant/system），并顺带刷新会话 updated_at（用于列表按活跃排序）。"""
    conn = target_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO message "
                "(conversation_id, role, msg_type, content, task_id, report_id) "
                "VALUES (%s, %s, %s, %s, %s, %s)",
                (conversation_id, role, msg_type, content, task_id, report_id),
            )
            cur.execute(
                "UPDATE conversation SET updated_at = CURRENT_TIMESTAMP WHERE id = %s",
                (conversation_id,),
            )
        conn.commit()
    finally:
        conn.close()


def get_messages(conversation_id: int) -> List[Dict[str, Any]]:
    """按 id 升序返回某会话的全部消息。"""
    conn = target_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, role, msg_type, content, task_id, report_id, created_at "
                "FROM message WHERE conversation_id=%s ORDER BY id",
                (conversation_id,),
            )
            return cur.fetchall()
    finally:
        conn.close()


def list_conversations(user_id: int) -> List[Dict[str, Any]]:
    """某用户的会话列表（按最近更新倒序）。"""
    conn = target_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, title, created_at, updated_at "
                "FROM conversation WHERE user_id=%s ORDER BY updated_at DESC",
                (user_id,),
            )
            return cur.fetchall()
    finally:
        conn.close()
