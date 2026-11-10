# -*- coding: utf-8 -*-
"""一次性脚本：按序执行 scripts/ddl/*.sql 建库建表（幂等，可重复跑）。

用法（必须用 D:/py/python.exe）：
    D:/py/python.exe scripts/ddl/run_ddl.py            # 执行全部 DDL
    D:/py/python.exe scripts/ddl/run_ddl.py 003 004    # 只执行指定编号
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

from app.db.connection import server_conn, TARGET_DB  # noqa: E402


def main() -> None:
    ddl_dir = Path(__file__).resolve().parent
    only = {a.zfill(3) for a in sys.argv[1:]}
    files = sorted(ddl_dir.glob("*.sql"))
    if only:
        files = [f for f in files if f.name[:3] in only]

    conn = server_conn()  # 连到服务端，再切目标库（DDL 无 USE 语句）
    try:
        with conn.cursor() as cur:
            cur.execute(f"CREATE DATABASE IF NOT EXISTS {TARGET_DB} "
                        "DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci")
            cur.execute(f"USE {TARGET_DB}")
        for f in files:
            sql = f.read_text(encoding="utf-8")
            # 逐条语句执行（DDL 内是纯 CREATE TABLE，无存储过程/触发器，简单按 ; 切安全）
            stmts = [s.strip() for s in sql.split(";") if s.strip()]
            with conn.cursor() as cur:
                for s in stmts:
                    cur.execute(s)
            conn.commit()
            print(f"  ✓ {f.name}  （{len(stmts)} 条语句）")
        print(f"完成：目标库 {TARGET_DB}，共 {len(files)} 个 DDL 文件")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
