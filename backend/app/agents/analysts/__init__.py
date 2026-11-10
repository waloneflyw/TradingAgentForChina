# -*- coding: utf-8 -*-
"""4 个工具型分析师：market / fundamentals / news / social。

每个模块暴露一个 create_xxx_analyst(llm) 闭包工厂，返回对应的节点函数，
供 app/graph/setup.py 组装图时调用。
"""
from app.agents.analysts.market_analyst import create_market_analyst
from app.agents.analysts.fundamentals_analyst import create_fundamentals_analyst
from app.agents.analysts.news_analyst import create_news_analyst
from app.agents.analysts.social_media_analyst import create_social_media_analyst

__all__ = [
    "create_market_analyst",
    "create_fundamentals_analyst",
    "create_news_analyst",
    "create_social_media_analyst",
]
