# -*- coding: utf-8 -*-
"""巨潮资讯网（cninfo）公告直连。

关键点（文档 §13.3/13.4，已实测 2026-09）：
- orgId **不可按规则推导**（600519→gssh0600519、600025→9900030360、601398→jjxt0000019、
  300750→GD165627，各不同）。权威来源：
  ① 深市全量 `szse_stock.json`（一次请求含主板+创业板，code→orgId）；
  ② 沪市/遗漏码用 `topSearch/query` 联想接口（逐码一次），本地缓存。
- 查询接口：POST http://www.cninfo.com.cn/new/hisAnnouncement/query
  stock=`代码,orgId`、column=`sse`(沪)/`szse`(深，含创业板)、seDate=`起~止`、pageNum 翻页。
- 公告时间 announcementTime 是毫秒时间戳 → Asia/Shanghai。
- adjunctUrl 形如 `finalpage/2026-08-15/1225475868.PDF`，完整链接 = static.cninfo.com.cn 前缀。
"""
from __future__ import annotations

import json
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests

from app.dataflows.symbols import exchange, to_bare

CST = timezone(timedelta(hours=8))

QUERY_URL = "http://www.cninfo.com.cn/new/hisAnnouncement/query"
TOPSEARCH_URL = "http://www.cninfo.com.cn/new/information/topSearch/query"
SZSE_LIST_URL = "http://www.cninfo.com.cn/new/data/szse_stock.json"
PDF_BASE = "http://static.cninfo.com.cn/"

_CACHE_FILE = Path(__file__).resolve().parent / ".cninfo_orgid_cache.json"

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "http://www.cninfo.com.cn/new/commonUrl/pageOfSearch?url=disclosure/list/search",
    "X-Requested-With": "XMLHttpRequest",
}

_lock = threading.Lock()
_szse_map: dict[str, str] | None = None
_disk_cache: dict[str, str] = {}


def _load_szse() -> dict[str, str]:
    """深市 code→orgId（含创业板），一次请求，内存缓存。"""
    global _szse_map
    if _szse_map is None:
        m: dict[str, str] = {}
        try:
            j = requests.get(SZSE_LIST_URL, headers=_HEADERS, timeout=30).json()
            lst = j if isinstance(j, list) else j.get("stockList", [])
            for s in lst or []:
                if s.get("code") and s.get("orgId"):
                    m[s["code"]] = s["orgId"]
        except Exception:
            pass  # 拿不到就退回逐码 topSearch
        _szse_map = m
    return _szse_map


def _load_disk_cache() -> dict[str, str]:
    global _disk_cache
    if not _disk_cache and _CACHE_FILE.exists():
        try:
            _disk_cache = json.loads(_CACHE_FILE.read_text(encoding="utf-8"))
        except Exception:
            _disk_cache = {}
    return _disk_cache


def _save_disk_cache() -> None:
    try:
        _CACHE_FILE.write_text(json.dumps(_disk_cache, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


def _post_retry(url: str, data: dict, retries: int = 3, timeout: int = 30) -> Any:
    """带重试的 POST（cninfo 偶发超时/断连）。"""
    last: Exception | None = None
    for i in range(retries):
        try:
            r = requests.post(url, headers=_HEADERS, data=data, timeout=timeout)
            r.raise_for_status()
            return r.json()
        except Exception as e:  # noqa: BLE001
            last = e
            if i < retries - 1:
                time.sleep(1.5 * (i + 1))
    raise RuntimeError(f"cninfo POST 失败 {retries} 次：{last}")


def _topsearch(code: str) -> str | None:
    j = _post_retry(TOPSEARCH_URL, {"keyWord": to_bare(code), "maxNum": "5"}, timeout=15)
    if j and j[0].get("orgId"):
        return j[0]["orgId"]
    return None


def org_id(code: str) -> str:
    """后缀代码 → cninfo orgId（优先深市映射，其次本地缓存，最后 topSearch）。"""
    bare = to_bare(code)
    ex = exchange(code)
    with _lock:
        cache = _load_disk_cache()
        if bare in cache:
            return cache[bare]
        oid: str | None = None
        if ex == "SZ":
            oid = _load_szse().get(bare)
        if not oid:
            oid = _topsearch(bare)
        if oid:
            cache[bare] = oid
            _disk_cache.update(cache)
            _save_disk_cache()
        if not oid:
            raise RuntimeError(f"cninfo 无法解析 orgId：{code}")
        return oid


def column_of(code: str) -> str:
    """后缀代码 → 查询 column（沪 sse / 深 szse，含创业板）。"""
    return "sse" if exchange(code) == "SH" else "szse"


def ms_to_cst(ms: int | str) -> datetime:
    """毫秒时间戳 → Asia/Shanghai 本地时间（无时区）。"""
    return datetime.fromtimestamp(int(ms) / 1000, tz=timezone.utc).astimezone(CST).replace(tzinfo=None)


def fetch_announcements(code: str, start: str, end: str,
                        page_size: int = 30, max_pages: int = 10) -> list[dict[str, Any]]:
    """拉取某股公告列表（含分页），返回标准化 dict 列表。

    返回字段：stock_code/title/url/announce_time/category。
    """
    oid = org_id(code)
    col = column_of(code)
    out: list[dict[str, Any]] = []
    for page in range(1, max_pages + 1):
        data = {
            "pageNum": str(page),
            "pageSize": str(page_size),
            "column": col,
            "tabName": "fulltext",
            "plate": "",
            "stock": f"{to_bare(code)},{oid}",
            "searchkey": "",
            "secid": "",
            "category": "",
            "trade": "",
            "seDate": f"{start}~{end}",
            "sortName": "",
            "sortType": "",
            "isHLtitle": "true",
        }
        j = _post_retry(QUERY_URL, data)
        anns = j.get("announcements") or []
        if not anns:
            break
        for a in anns:
            url = a.get("adjunctUrl") or ""
            if url and not url.startswith("http"):
                url = PDF_BASE + url
            out.append({
                "stock_code": f"{a.get('secCode', to_bare(code))}.{exchange(code)}",
                "title": a.get("announcementTitle", ""),
                "url": url,
                "announce_time": ms_to_cst(a["announcementTime"]) if a.get("announcementTime") else None,
                "category": (a.get("category") or None),
            })
        total = int(j.get("totalAnnouncement") or 0)
        if page * page_size >= total:
            break
    return out
