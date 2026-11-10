# -*- coding: utf-8 -*-
"""经理节点：研究经理（多空裁决）+ 基金经理（最终裁决）。"""
from app.agents.managers.research_manager import create_research_manager
from app.agents.managers.portfolio_manager import create_portfolio_manager

__all__ = ["create_research_manager", "create_portfolio_manager"]
