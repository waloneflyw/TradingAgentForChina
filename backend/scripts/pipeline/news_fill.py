# -*- coding: utf-8 -*-
"""新闻管道：财联社电报（全市场）+ 东财个股新闻 → news 表。

- 财联社电报：akshare stock_info_global_cls（内部已处理 cls 签名），stock_code 为空；
  akshare 不返回 url，用 (标题+时间) 的 md5 合成稳定去重 url（幂等）。
- 东财个股新闻：akshare stock_news_em（个股维度），stock_code 命中。
用法（tradingagents 环境）：
    python scripts/pipeline/news_fill.py                 # 只拉财联社全市场快讯
    python scripts/pipeline/news_fill.py --codes 600519.SH   # 追加个股新闻
"""
from __future__ import annotations

import argparse
import hashlib
import os
import sys
from datetime import datetime
from pathlib import Path

os.environ.setdefault("TQDM_DISABLE", "1")  # 静音 akshare 内部 tqdm 分页进度条

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # backend/

import akshare as ak  # noqa: E402

from app.dataflows import akshare_source as src  # noqa: E402
from app.dataflows.db_writer import upsert  # noqa: E402
from app.dataflows.symbols import to_bare, to_suffix  # noqa: E402
from app.db.connection import target_conn  # noqa: E402


def _cls_url(title: str, pub: str) -> str:
    h = hashlib.md5(f"{pub}|{title}".encode("utf-8")).hexdigest()[:16]
    return f"https://www.cls.cn/telegraph/{h}"


def _to_dt(date_s: str, time_s: str) -> datetime | None:
    try:
        return datetime.strptime(f"{date_s} {time_s}", "%Y-%m-%d %H:%M:%S")
    except Exception:
        return None


def fill_cls(conn=None) -> int:
    """财联社电报（全市场，20 条左右）→ news。"""
    df = src.call(ak.stock_info_global_cls, symbol="全部")
    rows = []
    for _, r in df.iterrows():
        title = str(r.get("标题") or "")
        content = str(r.get("内容") or "")
        pub = _to_dt(str(r.get("发布日期") or ""), str(r.get("发布时间") or ""))
        if not title or not pub:
            continue
        rows.append({
            "stock_code": None,
            "source": "cls",
            "url": _cls_url(title, pub.isoformat()),
            "title": title[:500],
            "content": content,
            "publish_time": pub,
        })
    return upsert("news", rows, ["source", "url"], conn=conn)


def fill_stock_news(code: str, conn=None) -> int:
    """东财个股新闻 → news（best-effort，接口列名可能随版本变）。"""
    bare = to_bare(code)
    suffix = to_suffix(code)
    df = src.call(ak.stock_news_em, symbol=bare)
    if df is None or len(df) == 0:
        return 0
    cols = list(df.columns)

    def pick(row, *names):
        for n in names:
            if n in cols and row.get(n) is not None:
                return row.get(n)
        return None

    rows = []
    for _, r in df.iterrows():
        title = str(pick(r, "新闻标题", "标题") or "")
        if not title:
            continue
        url = str(pick(r, "新闻链接", "链接", "url") or "")
        if not url:
            url = f"https://emweb.securities.eastmoney.com/news/{hashlib.md5(title.encode()).hexdigest()[:16]}"
        pub_raw = pick(r, "发布时间", "时间", "发布日期")
        pub = None
        if pub_raw:
            try:
                pub = datetime.strptime(str(pub_raw)[:19], "%Y-%m-%d %H:%M:%S")
            except Exception:
                pub = None
        rows.append({
            "stock_code": suffix,
            "source": "eastmoney",
            "url": url[:500],
            "title": title[:500],
            "content": str(pick(r, "新闻内容", "内容") or "") or None,
            "publish_time": pub or datetime.now(),
        })
    return upsert("news", rows, ["source", "url"], conn=conn)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--codes", help="逗号分隔代码，追加个股新闻")
    args = ap.parse_args()

    src.require("stock_info_global_cls")
    conn = target_conn()
    try:
        n = fill_cls(conn=conn)
        print(f"财联社电报：{n} 条")
        if args.codes:
            src.require("stock_news_em")
            for code in [to_suffix(c) for c in args.codes.split(",") if c.strip()]:
                m = fill_stock_news(code, conn=conn)
                print(f"{code} 个股新闻：{m} 条")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
