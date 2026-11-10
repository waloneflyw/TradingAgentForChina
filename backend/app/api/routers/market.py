# -*- coding: utf-8 -*-
"""阶段 5 · 前端数据端点（轻量只读，复用现有 dataflows/store，不改数据层逻辑）。

- GET /api/stocks/search            股票联想搜索（结构化）
- GET /api/stocks/{code}/kline      前复权日 K 线
- GET /api/stocks/{code}/quote      最新行情快照（结构化）
- GET /api/market/overview          大盘概览（文本）
- GET /api/reports                  历史报告列表
- GET /api/screener/structured      量化初筛（结构化候选池）
"""
from __future__ import annotations

import math
from datetime import date, datetime

from fastapi import APIRouter, HTTPException, Query

from app.api import store
from app.dataflows import assistant_data, market_overview
from app.dataflows.kline import load_qfq_kline
from app.dataflows.symbols import to_suffix

router = APIRouter(prefix="/api", tags=["market"])


def _json_safe(v):
    """把 pandas/numpy/Decimal/datetime 值转成 JSON 可序列化。"""
    if v is None:
        return None
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    if isinstance(v, float):
        return None if math.isnan(v) or math.isinf(v) else v
    if hasattr(v, "item"):  # numpy 标量
        return _json_safe(v.item())
    return v


# ---- 股票搜索 ----

@router.get("/stocks/search")
def search_stocks(
    keyword: str = Query(..., min_length=1, description="名称/代码/拼音关键字"),
    limit: int = Query(10, ge=1, le=50),
):
    rows = assistant_data.search_stocks(keyword, limit)
    return [{"stock_code": r["stock_code"], "name": r["name"], "pinyin": r["pinyin"],
             "industry_sw_l1": r["industry_sw_l1"], "is_st": r["is_st"]} for r in rows]


# ---- 行情快照 ----

@router.get("/stocks/{code}/quote")
def get_quote(code: str):
    snap = assistant_data.get_quote_row(to_suffix(code))
    if not snap:
        raise HTTPException(status_code=404, detail="无该股行情快照")
    return {k: _json_safe(v) for k, v in snap.items()}


# ---- K 线 ----

@router.get("/stocks/{code}/kline")
def get_kline(
    code: str,
    start: str = Query(..., description="开始日期 yyyy-mm-dd"),
    end: str = Query(..., description="结束日期 yyyy-mm-dd"),
):
    df = load_qfq_kline(code, start, end)
    if df.empty:
        return {"code": to_suffix(code), "bars": []}
    bars = [
        {
            "date": d.strftime("%Y-%m-%d") if hasattr(d, "strftime") else str(d)[:10],
            "open": round(float(o), 4),
            "high": round(float(h), 4),
            "low": round(float(l), 4),
            "close": round(float(c), 4),
            "volume": int(v) if v is not None and not math.isnan(v) else 0,
            "amount": round(float(a), 2) if a is not None and not math.isnan(a) else 0,
        }
        for d, o, h, l, c, v, a in zip(
            df["date"], df["open"], df["high"], df["low"], df["close"],
            df["volume"], df["amount"],
        )
    ]
    return {"code": to_suffix(code), "bars": bars}


# ---- 大盘概览 ----

@router.get("/market/overview")
def market_overview_view():
    return {"text": market_overview.get_market_overview(date.today().isoformat())}


# ---- 历史报告列表 ----

@router.get("/reports")
def list_reports(
    stock_code: str | None = Query(None),
    industry: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
):
    rows = store.search_reports(stock_code=stock_code, industry=industry, limit=limit)
    return [
        {
            "task_id": r["task_id"],
            "stock_code": r["stock_code"],
            "stock_name": r["stock_name"],
            "industry": r["industry"],
            "rating": r["rating"],
            "analysis_date": _json_safe(r["analysis_date"]),
            "summary": r["summary"],
            "create_time": _json_safe(r["create_time"]),
        }
        for r in rows
    ]


# ---- 结构化选股 ----

@router.get("/screener/structured")
def screener_structured(
    industry: str | None = Query(None),
    min_roe: float | None = Query(None),
    max_pe: float | None = Query(None),
    min_growth: float | None = Query(None),
    min_attention: float | None = Query(None),
    max_turnover: float | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
):
    rows = market_overview.screener_rows(
        industry=industry, min_roe=min_roe, max_pe=max_pe, min_growth=min_growth,
        min_attention=min_attention, max_turnover=max_turnover, limit=limit,
    )
    return [{k: _json_safe(v) for k, v in r.items()} for r in rows]
