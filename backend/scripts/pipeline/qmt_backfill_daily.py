# -*- coding: utf-8 -*-
"""QMT(xtquant) 日线补齐 + 每日增量落库。

解决 daily_bar 的两类缺口：
  1) 历史缺口：`market_daily` 迁移历史截至 2026-09-04，之后无新数据；
  2) 增量缺口：无「每日定时落库」调度，行情一直靠 akshare 按需补。

本脚本用 miniQMT 的 xtdata 拉「不复权」日线（dividend_type='none'），再用
`get_divid_factors` 的 dr 事件算法算前复权因子（与 backfill_adj_factor.py 同源，
避开 front/none 对送转股的负价 bug），幂等 upsert 到 ashare_agent.daily_bar。

默认「增量」模式：每只股票从 daily_bar 最新交易日的次日补齐到今天；收盘后跑一次
即等于「每日增量」。也可用 --start 强制从某日重拉覆盖（修历史缺口）。

用法（必须用 D:/py/python.exe，具备 xtquant + pymysql；miniQMT 需先启动并登录）：
  增量补齐到今天：   D:/py/python.exe backend/scripts/pipeline/qmt_backfill_daily.py
  指定股票：         D:/py/python.exe backend/scripts/pipeline/qmt_backfill_daily.py --codes 600519.SH,000001.SZ
  强制从某日重拉：   D:/py/python.exe backend/scripts/pipeline/qmt_backfill_daily.py --start 20260901
  试跑前 N 只验证：  D:/py/python.exe backend/scripts/pipeline/qmt_backfill_daily.py --limit 5
  全市场（含新上市）：D:/py/python.exe backend/scripts/pipeline/qmt_backfill_daily.py --universe union
"""
from __future__ import annotations

import argparse
import math
import sys
from datetime import date, timedelta
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # backend/

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from app.dataflows.db_writer import upsert  # noqa: E402
from app.db.connection import target_conn  # noqa: E402
from xtquant import xtdata  # noqa: E402

# 核心字段（不复权日线必需列）。pct_chg/amplitude 由 OHLC 现算，turnover_rate 留 NULL。
FIELDS = ["open", "high", "low", "close", "volume", "amount", "preClose", "suspendFlag"]
CHUNK = 500  # 每批下载/拉取的股票数，控制内存与接口压力


def _f(v):
    """numpy 值 → 安全 float（NaN/Inf/None → None）。"""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    if math.isnan(f) or math.isinf(f):
        return None
    return f


def _i(v):
    """numpy 值 → 安全 int（NaN/None → None）。"""
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _universe(conn, source: str, codes: str) -> list[str]:
    """股票池：db=现库去重；xtdata=miniQMT 全市场；union=两者并集（补新上市）。"""
    if codes:
        return [c.strip() for c in codes.split(",") if c.strip()]
    out: list[str] = []
    if source in ("db", "union"):
        with conn.cursor() as cur:
            cur.execute("SELECT DISTINCT stock_code FROM daily_bar ORDER BY stock_code")
            out = [r["stock_code"] for r in cur.fetchall()]
    if source in ("xtdata", "union"):
        known = set(out)
        try:
            extra = sorted(c for c in xtdata.get_stock_list_in_sector("沪深A股") if c not in known)
            out.extend(extra)
        except Exception as e:  # noqa: BLE001
            print(f"[universe] 从 xtdata 取全市场列表失败（miniQMT 未启动/未登录？）：{e}")
            if source == "xtdata":
                raise
    return out


def _latest_dates(conn, codes: list[str]) -> dict[str, str | None]:
    """每只股票在 daily_bar 的最新交易日（'YYYYMMDD' 或 None）。"""
    with conn.cursor() as cur:
        cur.execute("SELECT stock_code, MAX(trade_date) AS d FROM daily_bar GROUP BY stock_code")
        m = {r["stock_code"]: r["d"] for r in cur.fetchall()}
    return {c: (m[c].strftime("%Y%m%d") if c in m and m[c] else None) for c in codes}


def _adj_factor_map(code: str, dates: list[str]) -> dict[str, float]:
    """前复权因子 adj_factor(t) = 1 / ∏(dr_i | 除权日 > t)。与 backfill_adj_factor.py 同源。"""
    end = f"{date.today().year + 1}1231"
    ev = xtdata.get_divid_factors(code, "19900101", end)
    if ev is None or getattr(ev, "empty", True):
        return {}
    ev = ev.sort_index()
    event_dates = np.array(ev.index.tolist())          # 'YYYYMMDD' 升序
    drs = ev["dr"].astype(float).to_numpy()
    if not np.all(np.isfinite(drs)) or np.any(drs <= 0):
        return {}
    n = len(drs)
    suffix = np.ones(n + 1)
    for k in range(n - 1, -1, -1):
        suffix[k] = suffix[k + 1] * drs[k]
    k = np.searchsorted(event_dates, np.array(dates), side="right")
    factors = 1.0 / suffix[k]
    return {d: float(v) for d, v in zip(dates, factors)}


def _fetch(codes: list[str], start: str, end: str) -> dict[str, pd.DataFrame]:
    """下载 + 拉取一批股票的不复权日线。返回 {code: DataFrame}。"""
    out: dict[str, pd.DataFrame] = {}
    for i in range(0, len(codes), CHUNK):
        batch = codes[i:i + CHUNK]
        try:
            # download_history_data 只收单个代码；批量下载用 download_history_data2（收 list）。
            xtdata.download_history_data2(batch, period="1d", start_time=start, end_time=end)
            data = xtdata.get_market_data_ex(
                FIELDS, batch, period="1d", start_time=start, end_time=end,
                dividend_type="none", fill_data=False,
            )
        except Exception as e:  # noqa: BLE001
            print(f"[fetch] 批次 {i // CHUNK + 1} 下载/拉取失败（miniQMT 未启动？）：{e}")
            raise
        for code, df in data.items():
            if df is not None and len(df) > 0:
                out[code] = df
    return out


def _rows_for(code: str, df: pd.DataFrame, latest_ymd: str | None, compute_adj: bool) -> list[dict]:
    """一只股票的 DataFrame → daily_bar 行（只取增量日期，算复权因子）。"""
    if "time" in df.columns:
        dts = pd.to_datetime(df["time"])
    else:
        dts = pd.to_datetime(df.index.to_series())
    df = df.copy()
    df["_dt"] = dts.dt.strftime("%Y-%m-%d").to_numpy()
    df["_ymd"] = dts.dt.strftime("%Y%m%d").to_numpy()
    if latest_ymd:  # 增量：只保留比库内最新更新的日期，避免覆盖迁移数据
        df = df[df["_ymd"] > latest_ymd]
    if len(df) == 0:
        return []

    ymd = df["_ymd"].tolist()
    adj = _adj_factor_map(code, ymd) if compute_adj else {}

    rows: list[dict] = []
    for _, s in df.iterrows():
        o, h, l, c = _f(s.get("open")), _f(s.get("high")), _f(s.get("low")), _f(s.get("close"))
        pc = _f(s.get("preClose"))
        vol = _i(s.get("volume"))
        amt = _f(s.get("amount"))
        sus = _i(s.get("suspendFlag")) or 0
        pct = round((c - pc) / pc * 100, 4) if (c is not None and pc) else None
        amp = round((h - l) / pc * 100, 4) if (h is not None and l is not None and pc) else None
        rows.append({
            "stock_code": code,
            "trade_date": s["_dt"],
            "open": o, "high": h, "low": l, "close": c,
            "pre_close": pc, "pct_chg": pct, "amplitude": amp,
            "volume": vol, "amount": amt,
            "turnover_rate": None,
            "adj_factor": adj.get(s["_ymd"]),
            "suspend_flag": sus,
        })
    return rows


def main() -> None:
    ap = argparse.ArgumentParser(description="QMT 日线补齐/每日增量")
    ap.add_argument("--codes", default="", help="逗号分隔的股票代码（默认全库）")
    ap.add_argument("--limit", type=int, default=0, help="只处理前 N 只（试跑）")
    ap.add_argument("--start", default="", help="强制从该日(YYYYMMDD)重拉覆盖；缺省=增量")
    ap.add_argument("--end", default="", help="截至日(YYYYMMDD)，缺省=今天")
    ap.add_argument("--universe", default="db", choices=["db", "xtdata", "union"],
                    help="股票池来源：db=现库 / xtdata=全市场 / union=并集（补新上市）")
    ap.add_argument("--lookback", type=int, default=45, help="增量模式往前多取的自然日数")
    ap.add_argument("--no-adj", action="store_true", help="跳过复权因子计算（留 NULL，查询端按1）")
    args = ap.parse_args()

    end = args.end or date.today().strftime("%Y%m%d")
    if args.start:
        fetch_start = args.start
    else:
        fetch_start = (date.today() - timedelta(days=args.lookback)).strftime("%Y%m%d")

    conn = target_conn()
    try:
        codes = _universe(conn, args.universe, args.codes)
        if args.limit:
            codes = codes[:args.limit]
        preview = codes[:15] + (["..."] if len(codes) > 15 else [])
        print(f"待处理 {len(codes)} 只，区间 {fetch_start}~{end}：{preview}")

        latest = _latest_dates(conn, codes)
        total = 0
        for i in range(0, len(codes), CHUNK):
            batch = codes[i:i + CHUNK]
            data = _fetch(batch, fetch_start, end)
            rows: list[dict] = []
            for code in batch:
                df = data.get(code)
                if df is None or len(df) == 0:
                    continue
                if args.start:  # 强制重拉：该区间内全部写入（覆盖）
                    rows += _rows_for(code, df, None, not args.no_adj)
                else:           # 增量：只写比库内最新更新的日期
                    rows += _rows_for(code, df, latest.get(code), not args.no_adj)
            if rows:
                upsert("daily_bar", rows, ["stock_code", "trade_date"], conn=conn)
                total += len(rows)
            done = min(i + CHUNK, len(codes))
            print(f"  [{done}/{len(codes)}] 本批新增/覆盖 {len(rows)} 行")
        print(f"完成：共写入 {total} 行")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
