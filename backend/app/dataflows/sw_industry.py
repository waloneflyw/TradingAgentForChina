# -*- coding: utf-8 -*-
"""申万行业分类（股票 → 一级/二级行业）。

数据源：申万宏源研究官网（swsresearch.com）指数发布 API。比 legulegu 稳定——
官方、单个接口一次 page_size=10000 拉全成分，不存在 335 次逐个行业抓的限流问题。

接口（对应 akshare index_research_sw.py 的实现）：
- index_publish/current/?indextype=一级行业  → 一级行业指数列表（swindexcode + 名称，31 个）
- index_publish/current/?indextype=二级行业  → 二级行业指数列表（约 124 个）
- index_publish/details/component_stocks/?swindexcode=801010  → 该指数全部成分股

映射链：股票 ∈ 一级指数成分 → 一级名；股票 ∈ 二级指数成分 → 二级名。
申万 2021 分类下每只 A股恰属一个一级 + 一个二级，两层独立取并集即可，无需解析层级。
"""
from __future__ import annotations

import time
import warnings
from typing import Callable

import requests

from app.dataflows.symbols import to_suffix

_Report = Callable[[str], None]

_BASE = "https://www.swsresearch.com/institute-sw/api/index_publish/current/"
_CONS = "https://www.swsresearch.com/institute-sw/api/index_publish/details/component_stocks/"
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
}


def _get(url: str, params: dict) -> dict:
    """GET 申万官网 API，忽略 SSL 校验（其证书链不全，同 akshare verify=False）。"""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        r = requests.get(url, params=params, headers=_HEADERS, verify=False, timeout=30)
    r.raise_for_status()
    return r.json()


def list_sw_indices(indextype: str) -> list[tuple[str, str]]:
    """返回 [(指数代码, 指数名称)]，如 [('801010', '农林牧渔'), ...]。"""
    data = _get(_BASE, {"page": "1", "page_size": "200", "indextype": indextype})
    results = (data.get("data") or {}).get("results") or []
    return [(row["swindexcode"], row["swindexname"]) for row in results]


def list_index_constituents(swindexcode: str) -> list[str]:
    """返回某申万指数的全部成分股（后缀格式 600519.SH）。"""
    data = _get(_CONS, {"swindexcode": swindexcode, "page": "1", "page_size": "10000"})
    results = (data.get("data") or {}).get("results") or []
    out: list[str] = []
    for row in results:
        try:
            out.append(to_suffix(str(row["stockcode"])))
        except ValueError:
            continue  # 北交所/边缘代码 to_suffix 判不出交易所就跳过
    return out


def build_stock_industry(progress: _Report | None = None,
                         delay: float = 0.15,
                         ) -> dict[str, tuple[str, str]]:
    """构建 {后缀代码: (申万一级, 申万二级)} 反向索引。

    拉 31 个一级 + 约 124 个二级行业指数的成分股，每个指数 1 次请求。
    官方 API 稳定，失败即抛（调用方决定是否整趟重跑），无需按行业增量续跑。

    Returns:
        {后缀代码: (一级名, 二级名)}；某层缺失时为 ""。
    """
    l1 = list_sw_indices("一级行业")
    l2 = list_sw_indices("二级行业")
    if progress:
        progress(f"一级行业 {len(l1)} 个 / 二级行业 {len(l2)} 个，开始拉成分…")

    l1_of: dict[str, str] = {}
    for i, (code, name) in enumerate(l1):
        if delay:
            time.sleep(delay)
        l1_of.update({s: name for s in list_index_constituents(code)})
        if progress:
            progress(f"一级 {i + 1}/{len(l1)} {name}：累计 {len(l1_of)} 只")

    l2_of: dict[str, str] = {}
    for i, (code, name) in enumerate(l2):
        if delay:
            time.sleep(delay)
        l2_of.update({s: name for s in list_index_constituents(code)})
        if progress:
            progress(f"二级 {i + 1}/{len(l2)} {name}：累计 {len(l2_of)} 只")

    result: dict[str, tuple[str, str]] = {}
    for s in set(l1_of) | set(l2_of):
        result[s] = (l1_of.get(s, ""), l2_of.get(s, ""))
    return result
