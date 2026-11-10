# -*- coding: utf-8 -*-
"""A股代码格式转换。

三种格式（本服务约定）：
- 后缀（存库统一用）：`600519.SH` / `000001.SZ` / `300750.SZ`
- 前缀（三大报表接口用）：`SH600519` / `SZ000001`
- 裸代码（部分接口用）：`600519` / `000001`

交易所判断规则（沪深，不含北交所细分）：
- 沪：600/601/603/605/688/689
- 深：000/001/002/003/300/301
"""
from __future__ import annotations


def _exchange(num: str) -> str:
    if num.startswith(("600", "601", "603", "605", "688", "689")):
        return "SH"
    if num.startswith(("000", "001", "002", "003", "30")):
        return "SZ"  # 30 覆盖创业板 300/301/302…（如 302132 中航成飞）
    if num.startswith(("4", "8", "92")):
        return "BJ"
    raise ValueError(f"无法判断交易所：{num}")


def to_suffix(code: str) -> str:
    """任意格式 → 后缀格式（600519.SH）。"""
    code = code.strip().upper()
    if "." in code:
        num, ex = code.split(".", 1)
        return f"{num}.{ex}"
    if code.startswith(("SH", "SZ", "BJ")):
        return f"{code[2:]}.{code[:2]}"
    num = code.zfill(6)
    return f"{num}.{_exchange(num)}"


def to_prefix(code: str) -> str:
    """任意格式 → 前缀格式（SH600519），三大报表接口用。"""
    s = to_suffix(code)
    num, ex = s.split(".")
    return f"{ex}{num}"


def to_bare(code: str) -> str:
    """任意格式 → 裸 6 位代码（600519）。"""
    return to_suffix(code).split(".")[0]


def exchange(code: str) -> str:
    """任意格式 → 交易所（SH/SZ/BJ）。"""
    return to_suffix(code).split(".")[1]
