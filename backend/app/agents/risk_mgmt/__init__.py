# -*- coding: utf-8 -*-
"""风控三派辩论（激进/中性/保守）。"""
from app.agents.risk_mgmt.aggressive_debator import create_aggressive_debator
from app.agents.risk_mgmt.neutral_debator import create_neutral_debator
from app.agents.risk_mgmt.conservative_debator import create_conservative_debator

__all__ = [
    "create_aggressive_debator",
    "create_neutral_debator",
    "create_conservative_debator",
]
