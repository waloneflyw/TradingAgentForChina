// —— 前端领域类型，与后端 SSE 事件 / REST 结构对齐 ——

export type Rating = '买' | '增持' | '持有' | '减持' | '卖' | string

export interface StockSearchItem {
  stock_code: string
  name: string
  pinyin: string
  industry_sw_l1: string | null
  is_st: number
}

export interface KlineBar {
  date: string
  open: number
  high: number
  low: number
  close: number
  volume: number
  amount: number
}

export interface Quote {
  trade_date: string
  stock_name: string
  latest_price: number
  pct_change: number
  pe: number | null
  turnover_rate: number | null
  composite_score: number | null
  comment_rank: number | null
  attention_index: number | null
  hot_rank: number | null
}

export interface ScreenerRow {
  stock_code: string
  name: string
  industry_sw_l1: string | null
  roe: number | null
  net_profit_growth: number | null
  gross_margin: number | null
  latest_price: number | null
  pct_change: number | null
  pe: number | null
  turnover_rate: number | null
  composite_score: number | null
  attention_index: number | null
  comment_rank: number | null
}

export interface ReportSummary {
  task_id: string
  stock_code: string
  stock_name: string
  industry: string | null
  rating: string
  analysis_date: string
  summary: string
  create_time: string
}

export interface FullReport {
  task_id: string
  stock_code: string
  stock_name: string | null
  industry: string | null
  rating: string
  analysis_date: string
  summary: string
  report_json: {
    company_of_interest?: string
    trade_date?: string
    market_report?: string
    sentiment_report?: string
    news_report?: string
    fundamentals_report?: string
    investment_plan?: string
    trader_investment_plan?: string
    final_trade_decision?: string
    disclaimer?: string
    rating?: string
  }
}

// —— SSE 事件（/api/chat/stream 与 /api/analysis 共用命名空间）——

export interface SseNodeEvent {
  type: 'node'
  name: string
  phase: 'start' | 'end'
}
export interface SseToolEvent {
  type: 'tool'
  name: string
  phase: 'call' | 'result'
  detail?: string
  node?: string
}
export interface SseReportEvent {
  type: 'report'
  analyst: string
  report: string
}
export interface SseColleagueEvent {
  type: 'colleague'
  name: 'run_stock_analysis' | 'run_screener'
  phase: 'start' | 'end' | 'error'
  detail?: string
  task_id?: string
  rating?: Rating
}
export interface SseAssistantEvent {
  type: 'assistant'
  content: string
}
export interface SseAssistantDeltaEvent {
  type: 'assistant_delta'
  content: string
}
export interface SseMetaEvent {
  type: 'meta'
  conversation_id?: number
  task_id?: string
  code?: string
  date?: string
}
export interface SseDoneEvent {
  type: 'done'
  conversation_id?: number
  task_id?: string
  rating?: Rating
  summary?: string
  decision?: string
  stock_name?: string
  industry?: string
}
export interface SseErrorEvent {
  type: 'error'
  message: string
}

export type SseEvent =
  | SseNodeEvent
  | SseToolEvent
  | SseReportEvent
  | SseColleagueEvent
  | SseAssistantEvent
  | SseAssistantDeltaEvent
  | SseMetaEvent
  | SseDoneEvent
  | SseErrorEvent

// —— 任务运行时（「调用同事」卡片 → 报告卡片）——

export type NodeStatus = 'waiting' | 'running' | 'done' | 'failed'

export interface NodeState {
  status: NodeStatus
  startedAt?: number
  elapsedMs?: number
}

export interface ToolCallRecord {
  name: string
  phase: 'call' | 'result'
  detail?: string
  node?: string
  at: number
}

export interface ReportChunk {
  analyst: string
  content: string
}

export interface TaskRuntime {
  kind: 'analysis' | 'screener'
  title: string
  status: 'running' | 'done' | 'error'
  taskId?: string
  rating?: Rating
  stockCode?: string
  stockName?: string
  industry?: string
  detail?: string
  error?: string
  // 分析任务专用：过程事件缓冲
  nodes: Record<string, NodeState>
  tools: ToolCallRecord[]
  reports: ReportChunk[]
}

// —— 聊天消息（判别联合）——

export type ChatMessage =
  | { id: string; role: 'user'; content: string }
  | { id: string; role: 'assistant'; content: string }
  | { id: string; role: 'system'; content: string }
  | { id: string; role: 'task'; task: TaskRuntime }

export interface ConversationItem {
  id: number
  title: string | null
  created_at: string
  updated_at: string
}

export interface ConversationMessage {
  id: number
  role: string
  msg_type: string
  content: string
  task_id: string | null
  report_id: number | null
  created_at: string
}
