"""数据层适配（阶段 1 数据管道 + 阶段 2 工具薄壳共用）。

子模块：
- symbols       代码格式转换（后缀/前缀/裸代码）
- akshare_source akshare 统一封装（dir 自检 / 限流 / 重试）
- financial_map 东财报表项 code → 中文行名 + 财务指标列映射
- sw_industry   申万行业分类（股票 → 一级/二级）
- cninfo        巨潮公告直连
- db_writer     目标库通用 upsert（幂等落库）
"""
