# -*- coding: utf-8 -*-
"""一次性脚本：fastapi_db.market_daily → ashare_agent.daily_bar

- 只读源库（fastapi_db），写入目标库（ashare_agent）。
- 按「年」分批，幂等可续跑：某年已迁满则跳过，未满则清空重灌。
- 同一 MySQL 实例上跨库 INSERT...SELECT，无 Python 侧数据搬运开销。

用法（必须用 D:/py/python.exe，它同时有 pymysql + xtquant）：
    D:/py/python.exe backend/scripts/migrate/migrate_daily_bar.py
"""
from __future__ import annotations

import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # backend/

import pymysql

from app.config import Config, check_credentials
from app.db.connection import source_conn, target_conn

# 源列表达式 → 目标列名
# - settelementPrice / openInterest 是期货遗留字段，丢弃；
# - suspendFlag 源可为 NULL，按 0=正常 兜底（daily_bar.suspend_flag 为 NOT NULL）。
_COLUMNS = [
    ("stock_code", "stock_code"),
    ("trade_date", "trade_date"),
    ("open", "open"),
    ("high", "high"),
    ("low", "low"),
    ("close", "close"),
    ("preClose", "pre_close"),
    ("pct_chg", "pct_chg"),
    ("amplitude", "amplitude"),
    ("volume", "volume"),
    ("amount", "amount"),
    ("turnover_rate", "turnover_rate"),
    ("COALESCE(suspendFlag, 0)", "suspend_flag"),
]

_SRC_COLS = ", ".join(src for src, _ in _COLUMNS)
_DST_COLS = ", ".join(dst for _, dst in _COLUMNS)


def _stmt(path: Path) -> str:
    """读 DDL 文件，去掉注释行与结尾分号，返回可执行单语句。"""
    return path.read_text(encoding="utf-8").strip().rstrip(";").strip()


def ensure_schema() -> None:
    """建库建表（幂等）。DDL 与 scripts/ddl/*.sql 保持一致。"""
    ddl_dir = Path(__file__).resolve().parents[1] / "ddl"
    # 1) 建库：连到 MySQL 系统层执行
    root = pymysql.connect(
        host=Config.DB_HOST, port=Config.DB_PORT,
        user=Config.DB_USER, password=Config.DB_PASSWORD,
        charset=Config.DB_CHARSET, autocommit=True,
    )
    try:
        with root.cursor() as cur:
            cur.execute(_stmt(ddl_dir / "001_create_database.sql"))
    finally:
        root.close()
    # 2) 建表：连到目标库执行
    with target_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(_stmt(ddl_dir / "002_create_daily_bar.sql"))
        conn.commit()
    print("建库建表完成：ashare_agent.daily_bar")


def year_ranges(src) -> list[tuple[int, int]]:
    """源库逐年的 (year, count)。"""
    with src.cursor() as cur:
        cur.execute(
            "SELECT YEAR(trade_date) AS y, COUNT(*) AS n "
            "FROM market_daily GROUP BY y ORDER BY y"
        )
        return [(r["y"], r["n"]) for r in cur.fetchall()]


def main() -> None:
    check_credentials()
    ensure_schema()

    src = source_conn()
    dst = target_conn()
    try:
        years = year_ranges(src)
        print(f"源库共 {len(years)} 个年份，开始迁移...")
        total = 0
        for y, n in years:
            lo, hi = f"{y}-01-01", f"{y + 1}-01-01"
            with dst.cursor() as cur:
                cur.execute(
                    "SELECT COUNT(*) AS n FROM daily_bar "
                    "WHERE trade_date >= %s AND trade_date < %s", (lo, hi)
                )
                done = cur.fetchone()["n"]
            if done >= n:
                print(f"  {y}: 已迁移 {done} 行，跳过")
                total += done
                continue
            # 幂等：先清空该年在目标库的残留，再整年重灌
            sql = (
                f"INSERT INTO daily_bar ({_DST_COLS}) "
                f"SELECT {_SRC_COLS} FROM {Config.SOURCE_DB}.market_daily "
                f"WHERE trade_date >= %s AND trade_date < %s"
            )
            with dst.cursor() as cur:
                cur.execute(
                    "DELETE FROM daily_bar WHERE trade_date >= %s AND trade_date < %s",
                    (lo, hi),
                )
                cur.execute(sql, (lo, hi))
            dst.commit()
            total += n
            print(f"  {y}: 迁入 {n} 行")
        print(f"迁移完成，目标库累计 {total} 行")
    finally:
        src.close()
        dst.close()


if __name__ == "__main__":
    main()
