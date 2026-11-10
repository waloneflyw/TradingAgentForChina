# -*- coding: utf-8 -*-
"""合规护栏 ④：敏感兜底（后端关键词拦截 + 日志）。

命中的不是「拒绝服务」，而是「记日志 + 提示金融助手转回免责话术」——软拦截。
四条敏感线（对应需求分析 §2.7 ④）：荐股承诺 / 代客理财 / 内幕消息 / 具体点位承诺。
"""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

# (标签, 正则)。命中任一即触发软拦截。
SENSITIVE_PATTERNS: List[Tuple[str, str]] = [
    ("收益承诺", r"保证(翻倍|赚钱|盈利|收益)|稳赚|必涨|包赚|保底|不赔|一夜暴富|承诺(收益|回报)"),
    ("代客理财", r"代(客|为|我)(理财|操盘|操作|下单)|账户托管|托管账户|帮我(操盘|炒股)"),
    ("内幕消息", r"内幕|内部消息|老鼠仓|庄家|提前知道|消息面(保真|一手)"),
    ("点位承诺", r"明天涨到|一定(涨|跌)|肯定(涨|跌)|必然(涨|跌)|保证(涨|跌)到|目标价保证"),
]

_LOG_PATH = Path(__file__).resolve().parents[2] / "logs" / "compliance.log"


def check_sensitive(text: str) -> List[str]:
    """返回命中的敏感类别标签列表（去重），未命中为空。"""
    hits: List[str] = []
    for label, pattern in SENSITIVE_PATTERNS:
        if re.search(pattern, text or "", flags=re.IGNORECASE):
            hits.append(label)
    return hits


def log_sensitive(
    conversation_id: Optional[int],
    message: str,
    hits: List[str],
) -> None:
    """追加一条合规拦截日志（含时间/会话/命中类别/原文摘要）。"""
    try:
        _LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().isoformat(timespec="seconds")
        snippet = (message or "").replace("\n", " ")[:200]
        with open(_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(f"{ts} | conv={conversation_id} | 命中={','.join(hits)} | {snippet}\n")
    except Exception:  # 日志写失败不影响主流程
        pass
