// REST 端点封装（对应后端 app/api/routers/market.py + analysis + chat）。
import { http } from './http'
import type {
  KlineBar,
  Quote,
  ReportSummary,
  FullReport,
  ScreenerRow,
  StockSearchItem,
  ConversationItem,
  ConversationMessage,
} from '../types'

export interface KlineResp {
  code: string
  bars: KlineBar[]
}

export function searchStocks(keyword: string, limit = 10): Promise<StockSearchItem[]> {
  return http.get<StockSearchItem[]>(`/api/stocks/search?keyword=${encodeURIComponent(keyword)}&limit=${limit}`)
}

export function getQuote(code: string): Promise<Quote> {
  return http.get<Quote>(`/api/stocks/${encodeURIComponent(code)}/quote`)
}

export function getKline(code: string, start: string, end: string): Promise<KlineResp> {
  return http.get<KlineResp>(
    `/api/stocks/${encodeURIComponent(code)}/kline?start=${start}&end=${end}`,
  )
}

export function getMarketOverview(): Promise<{ text: string }> {
  return http.get<{ text: string }>('/api/market/overview')
}

export function listReports(params: {
  stock_code?: string
  industry?: string
  limit?: number
} = {}): Promise<ReportSummary[]> {
  const q = new URLSearchParams()
  if (params.stock_code) q.set('stock_code', params.stock_code)
  if (params.industry) q.set('industry', params.industry)
  q.set('limit', String(params.limit ?? 20))
  return http.get<ReportSummary[]>(`/api/reports?${q.toString()}`)
}

export function getReport(taskId: string): Promise<FullReport> {
  return http.get<FullReport>(`/api/analysis/${encodeURIComponent(taskId)}`)
}

export interface ScreenerParams {
  industry?: string
  min_roe?: number
  max_pe?: number
  min_growth?: number
  min_attention?: number
  max_turnover?: number
  limit?: number
}

export function screenerStructured(params: ScreenerParams): Promise<ScreenerRow[]> {
  const q = new URLSearchParams()
  if (params.industry) q.set('industry', params.industry)
  if (params.min_roe != null) q.set('min_roe', String(params.min_roe))
  if (params.max_pe != null) q.set('max_pe', String(params.max_pe))
  if (params.min_growth != null) q.set('min_growth', String(params.min_growth))
  if (params.min_attention != null) q.set('min_attention', String(params.min_attention))
  if (params.max_turnover != null) q.set('max_turnover', String(params.max_turnover))
  q.set('limit', String(params.limit ?? 50))
  return http.get<ScreenerRow[]>(`/api/screener/structured?${q.toString()}`)
}

export function listConversations(): Promise<{ conversations: ConversationItem[] }> {
  return http.get<{ conversations: ConversationItem[] }>('/api/conversations')
}

export function getConversationMessages(id: number): Promise<{ messages: ConversationMessage[] }> {
  return http.get<{ messages: ConversationMessage[] }>(`/api/conversations/${id}/messages`)
}
