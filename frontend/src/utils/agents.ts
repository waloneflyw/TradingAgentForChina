// 12 个 agent 节点（与后端 analysis_service.AGENT_NODES 一致）+ 4 阶段布局 + 中文名。

export interface AgentDef {
  name: string
  label: string
  stage: number
}

export const AGENT_NODES: AgentDef[] = [
  { name: 'Market Analyst', label: '市场分析师', stage: 0 },
  { name: 'Social Analyst', label: '社媒分析师', stage: 0 },
  { name: 'News Analyst', label: '新闻分析师', stage: 0 },
  { name: 'Fundamentals Analyst', label: '基本面分析师', stage: 0 },
  { name: 'Bull Researcher', label: '牛方研究员', stage: 1 },
  { name: 'Bear Researcher', label: '熊方研究员', stage: 1 },
  { name: 'Research Manager', label: '研究经理', stage: 2 },
  { name: 'Trader', label: '交易员', stage: 3 },
  { name: 'Aggressive Analyst', label: '激进风控师', stage: 3 },
  { name: 'Neutral Analyst', label: '中性风控师', stage: 3 },
  { name: 'Conservative Analyst', label: '保守风控师', stage: 3 },
  { name: 'Portfolio Manager', label: '组合经理', stage: 3 },
]

export const STAGE_LABELS = ['① 四大分析师', '② 牛熊辩论', '③ 研究经理汇总', '④ 交易与风控']

export function nodesByStage(): AgentDef[][] {
  const groups: AgentDef[][] = [[], [], [], []]
  for (const n of AGENT_NODES) groups[n.stage].push(n)
  return groups
}

// —— 工具名 → 中文标签 + 数据来源（过程/依据页展示用） ——
export const TOOL_META: Record<string, { label: string; source: string }> = {
  get_stock_data: { label: '股价数据', source: 'MySQL/akshare' },
  get_indicators: { label: '技术指标', source: 'MySQL/akshare' },
  get_fundamentals: { label: '基本面快照', source: 'MySQL' },
  get_financial_statements: { label: '三大报表', source: 'MySQL' },
  get_news: { label: '个股新闻', source: 'akshare' },
  get_announcements: { label: '公司公告', source: 'akshare' },
  get_shareholder_changes: { label: '股东增减持', source: 'akshare' },
  get_market_overview: { label: '大盘概览', source: 'akshare' },
  get_stock_screener: { label: '选股初筛', source: 'MySQL' },
}

export function toolLabel(name: string): string {
  return TOOL_META[name]?.label ?? name
}

export function toolSource(name: string): string {
  return TOOL_META[name]?.source ?? '数据层'
}

// agent 节点名 → 四份分析师报告的中文标签（对应「结论」/「精简结论」）
export const AGENT_TO_REPORT: Record<string, string> = {
  'Market Analyst': '技术面',
  'Social Analyst': '情绪面',
  'News Analyst': '新闻面',
  'Fundamentals Analyst': '基本面',
}

// 非分析师节点的「精简结论」来源（report_json 字段，仅分析完成后可从全文取）
export const AGENT_PLAN_FIELD: Record<string, string> = {
  'Research Manager': 'investment_plan',
  Trader: 'trader_investment_plan',
  'Portfolio Manager': 'final_trade_decision',
}
