# -*- coding: utf-8 -*-
"""一次性脚本：列出所有存在 dr<1（缩股/反向拆股）事件的股票。

用于校验 daily_bar.adj_factor > 1 的股票是否全部来自缩股事件。
adj_factor = 1 / ∏(dr_i)，dr<1 时因子>1，是合法前复权语义，非算法 bug。
"""
from __future__ import annotations

import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.db.connection import target_conn  # noqa: E402
from xtquant import xtdata  # noqa: E402


def main() -> None:
    conn = target_conn()
    with conn.cursor() as cur:
        cur.execute("SELECT DISTINCT stock_code FROM daily_bar ORDER BY stock_code")
        codes = [r["stock_code"] for r in cur.fetchall()]
    conn.close()

    hit = []
    for code in codes:
        ev = xtdata.get_divid_factors(code, "19900101", "20261231")
        if ev is None or ev.empty:
            continue
        for d, row in ev.iterrows():
            dr = float(row["dr"])
            if dr < 0.999:
                hit.append((code, d, dr))
                break
    print(f"共 {len(codes)} 只，存在 dr<1（缩股）事件的股票 {len(hit)} 只：")
    for code, d, dr in hit:
        print(f"  {code}  缩股除权日={d}  dr={dr}")


if __name__ == "__main__":
    main()
