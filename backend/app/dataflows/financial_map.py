# -*- coding: utf-8 -*-
"""财务数据映射：东财英文 item code → 中文行名 + 财务指标列映射。

三大报表（stock_*_sheet_by_report_em）返回宽表，每列是一个报表项（英文 code）。
竖表落库时：核心项映射成中文行名，未覆盖项按英文 code 原样入库（不丢数据）。

财务指标（stock_financial_analysis_indicator_em）列 → financial_indicator 表列。
估值类（pe/pb/dividend_yield/total_market_cap）随行情逐日变化，由后续「每日估值快照」
任务写入，本报告期管道不填（留 NULL）。
"""
from __future__ import annotations

# ---- 三大报表：英文 code → 中文行名（仅核心常用项）----

BALANCE_MAP = {
    "MONETARYFUNDS": "货币资金",
    "ACCOUNTS_RECE": "应收账款",
    "NOTE_ACCOUNTS_RECE": "应收票据及应收账款",
    "PREPAYMENT": "预付款项",
    "INVENTORY": "存货",
    "TOTAL_CURRENT_ASSETS": "流动资产合计",
    "FIXED_ASSET": "固定资产",
    "CIP": "在建工程",
    "GOODWILL": "商誉",
    "INTANGIBLE_ASSET": "无形资产",
    "LONG_EQUITY_INVEST": "长期股权投资",
    "TOTAL_NONCURRENT_ASSETS": "非流动资产合计",
    "TOTAL_ASSETS": "资产总计",
    "SHORT_LOAN": "短期借款",
    "ACCOUNTS_PAYABLE": "应付账款",
    "CONTRACT_LIAB": "合同负债",
    "TOTAL_CURRENT_LIAB": "流动负债合计",
    "LONG_LOAN": "长期借款",
    "BOND_PAYABLE": "应付债券",
    "TOTAL_NONCURRENT_LIAB": "非流动负债合计",
    "TOTAL_LIABILITIES": "负债合计",
    "SHARE_CAPITAL": "实收资本(股本)",
    "CAPITAL_RESERVE": "资本公积",
    "SURPLUS_RESERVE": "盈余公积",
    "UNASSIGN_RPOFIT": "未分配利润",
    "TOTAL_PARENT_EQUITY": "归属于母公司股东权益合计",
    "MINORITY_EQUITY": "少数股东权益",
    "TOTAL_EQUITY": "股东权益合计",
    "TOTAL_LIABILITIES_EQUITY": "负债和股东权益总计",
}

INCOME_MAP = {
    "TOTAL_OPERATE_INCOME": "营业总收入",
    "OPERATE_INCOME": "营业收入",
    "TOTAL_OPERATE_COST": "营业总成本",
    "OPERATE_COST": "营业成本",
    "OPERATE_TAX_ADD": "税金及附加",
    "SALE_EXPENSE": "销售费用",
    "MANAGE_EXPENSE": "管理费用",
    "RESEARCH_EXPENSE": "研发费用",
    "FINANCE_EXPENSE": "财务费用",
    "INTEREST_EXPENSE": "利息费用",
    "OPERATE_PROFIT": "营业利润",
    "TOTAL_PROFIT": "利润总额",
    "INCOME_TAX": "所得税费用",
    "NETPROFIT": "净利润",
    "PARENT_NETPROFIT": "归属于母公司股东的净利润",
    "MINORITY_INTEREST": "少数股东损益",
    "BASIC_EPS": "基本每股收益",
    "DILUTED_EPS": "稀释每股收益",
    "COMPREHENSIVE_INCOME": "其他综合收益",
}

CASHFLOW_MAP = {
    "SALES_SERVICES": "销售商品、提供劳务收到的现金",
    "NETCASH_OPERATE": "经营活动产生的现金流量净额",
    "NETCASH_INVEST": "投资活动产生的现金流量净额",
    "NETCASH_FINANCE": "筹资活动产生的现金流量净额",
    "CCE_ADD": "现金及现金等价物净增加额",
    "END_CCE": "期末现金及现金等价物余额",
    "BEGIN_CCE": "期初现金及现金等价物余额",
}

STATEMENT_MAP = {
    "balance": BALANCE_MAP,
    "income": INCOME_MAP,
    "cashflow": CASHFLOW_MAP,
}

# ---- 财务指标：financial_indicator 表列 ← 东财指标列 ----

INDICATOR_COL_MAP = {
    "eps": "EPSJB",                      # 基本每股收益(元)
    "roe": "ROEJQ",                      # 净资产收益率-加权(%)
    "roa": "ZZCJLL",                     # 总资产净利率(%)
    "revenue_growth": "TOTALOPERATEREVETZ",   # 营业总收入同比(%)
    "net_profit_growth": "PARENTNETPROFITTZ",  # 归母净利润同比(%)
    "gross_margin": "XSMLL",             # 销售毛利率(%)
    "net_margin": "XSJLL",               # 销售净利率(%)
}
# 估值类（pe/pb/dividend_yield/total_market_cap）不在报告期指标接口里，见模块 docstring。

# 三大报表接口的元数据列（非报表项，熔宽表时要剔除）
STATEMENT_META_COLS = frozenset({
    "SECUCODE", "SECURITY_CODE", "SECURITY_NAME_ABBR", "ORG_CODE", "ORG_TYPE",
    "SECURITY_TYPE_CODE", "REPORT_DATE", "REPORT_TYPE", "REPORT_DATE_NAME",
    "NOTICE_DATE", "UPDATE_DATE", "CURRENCY",
})
