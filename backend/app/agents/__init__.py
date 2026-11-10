# -*- coding: utf-8 -*-
"""Agent 编排层：单股分析 11-agent 流水线 + 选股 agent + 金融助手。

子包结构（自底向上）：
- utils/      状态定义（agent_states）、公共小工具（agent_utils）、情境记忆（memory）
- analysts/   4 个工具型分析师（market/fundamentals/news/social）
- researchers/ 牛熊研究员（多空辩论）
- managers/   研究经理 + 组合经理
- trader/     交易员
- risk_mgmt/  风控三派辩论（aggressive/neutral/conservative）
- 顶层         screener.py（选股）+ assistant.py（金融助手）
"""
