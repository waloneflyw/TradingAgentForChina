import { defineStore } from 'pinia'
import { streamSse } from '../api/sse'
import { listConversations, getConversationMessages } from '../api'
import type { ChatMessage, TaskRuntime, SseEvent } from '../types'

let seq = 0
const uid = () => `m${Date.now().toString(36)}_${(seq++).toString(36)}`

export const useChatStore = defineStore('chat', {
  state: () => ({
    conversations: [] as { id: number; title: string | null; updated_at: string }[],
    currentConvId: null as number | null,
    messages: [] as ChatMessage[],
    streaming: false,
    /** task_id → 运行时（与消息里的 task 对象同引用，供工作台读取过程事件） */
    runtimes: {} as Record<string, TaskRuntime>,
    /** 正在构造中的任务（colleague start 之后、end 之前，尚无 task_id） */
    pendingTask: null as TaskRuntime | null,
    /** 当前正在收流的任务运行时（分析/选股均可） */
    activeTask: null as TaskRuntime | null,
  }),

  getters: {
    hasMessages: (s) => s.messages.length > 0,
  },

  actions: {
    async loadConversations() {
      try {
        const res = await listConversations()
        this.conversations = res.conversations
      } catch {
        /* 后端未起时静默 */
      }
    },

    newConversation() {
      this.currentConvId = null
      this.messages = []
      this.runtimes = {}
      this.pendingTask = null
      this.activeTask = null
    },

    async selectConversation(id: number) {
      this.currentConvId = id
      this.messages = []
      this.runtimes = {}
      try {
        const res = await getConversationMessages(id)
        this.messages = res.messages.map((m) => {
          if (m.role === 'user') return { id: uid(), role: 'user' as const, content: m.content }
          if (m.role === 'assistant') return { id: uid(), role: 'assistant' as const, content: m.content }
          return { id: uid(), role: 'system' as const, content: m.content }
        })
      } catch {
        /* ignore */
      }
    },

    /** 发送一条聊天消息，走 /api/chat/stream。 */
    async sendMessage(text: string) {
      if (this.streaming || !text.trim()) return
      this.streaming = true
      this.pendingTask = null
      this.activeTask = null

      this.messages.push({ id: uid(), role: 'user', content: text })
      const replyId = uid()
      this.messages.push({ id: replyId, role: 'assistant', content: '' })

      const replyMsg = () => this.messages.find((m) => m.id === replyId)

      await new Promise<void>((resolve) => {
        let finished = false
        const finish = () => {
          if (finished) return
          finished = true
          this.streaming = false
          resolve()
        }

        streamSse(
          '/api/chat/stream',
          { conversation_id: this.currentConvId, message: text },
          (event, data) => this.handleChatEvent(event, data as SseEvent, replyId),
          (err) => {
            const m = replyMsg()
            if (m && m.role === 'assistant' && !m.content) {
              m.content = `⚠️ 连接中断：${err.message}`
            }
            finish()
          },
          () => finish(),
        )
      })

      void this.loadConversations()
    },

    handleChatEvent(event: string, data: SseEvent, replyId: string) {
      const replyMsg = () => this.messages.find((m) => m.id === replyId)

      switch (event) {
        case 'meta':
          break

        case 'colleague': {
          const d = data as Extract<SseEvent, { type: 'colleague' }>
          if (d.phase === 'start') {
            const kind = d.name === 'run_stock_analysis' ? 'analysis' : 'screener'
            const task: TaskRuntime = {
              kind,
              title: kind === 'analysis' ? `正在分析 ${d.detail ?? ''}` : `正在选股 ${d.detail ?? ''}`,
              status: 'running',
              detail: d.detail,
              nodes: {},
              tools: [],
              reports: [],
            }
            this.pendingTask = task
            this.activeTask = task
            this.messages.push({ id: uid(), role: 'task', task })
          } else if (d.phase === 'end' && this.pendingTask) {
            const t = this.pendingTask
            t.status = 'done'
            t.rating = d.rating
            t.detail = d.detail
            if (d.task_id) {
              t.taskId = d.task_id
              this.runtimes[d.task_id] = t
            }
            this.pendingTask = null
          } else if (d.phase === 'error' && this.pendingTask) {
            const t = this.pendingTask
            t.status = 'error'
            t.error = d.detail
            this.pendingTask = null
          }
          break
        }

        case 'node': {
          const d = data as Extract<SseEvent, { type: 'node' }>
          if (!this.activeTask) break
          const st = this.activeTask.nodes[d.name] ?? { status: 'waiting' as const }
          if (d.phase === 'start') {
            st.status = 'running'
            st.startedAt = Date.now()
          } else {
            st.status = 'done'
            st.elapsedMs = st.startedAt ? Date.now() - st.startedAt : undefined
          }
          this.activeTask.nodes[d.name] = st
          break
        }

        case 'tool': {
          const d = data as Extract<SseEvent, { type: 'tool' }>
          if (!this.activeTask) break
          this.activeTask.tools.push({ name: d.name, phase: d.phase, detail: d.detail, node: d.node, at: Date.now() })
          break
        }

        case 'report': {
          const d = data as Extract<SseEvent, { type: 'report' }>
          if (!this.activeTask) break
          this.activeTask.reports.push({ analyst: d.analyst, content: d.report })
          break
        }

        case 'assistant': {
          const d = data as Extract<SseEvent, { type: 'assistant' }>
          const m = replyMsg()
          if (m && m.role === 'assistant') m.content = d.content
          break
        }

        case 'assistant_delta': {
          const d = data as Extract<SseEvent, { type: 'assistant_delta' }>
          const m = replyMsg()
          if (m && m.role === 'assistant') m.content += d.content
          break
        }

        case 'done': {
          const d = data as Extract<SseEvent, { type: 'done' }>
          if (d.conversation_id != null) this.currentConvId = d.conversation_id
          break
        }

        case 'error': {
          const d = data as Extract<SseEvent, { type: 'error' }>
          const m = replyMsg()
          if (m && m.role === 'assistant' && !m.content) m.content = `⚠️ ${d.message}`
          else this.messages.push({ id: uid(), role: 'system', content: `⚠️ ${d.message}` })
          break
        }
      }
    },

    /** 「个股深度分析」按钮直达：选股后插入用户消息 → chat 流。 */
    sendAnalysis(code: string, name: string) {
      void this.sendMessage(`请帮我深度分析 ${name}（${code}）`)
    },

    /** 「标签选股」按钮直达（聊天通道：跑 run_screener 出文字摘要）。 */
    sendScreener(query: string) {
      void this.sendMessage(`请帮我按以下条件选股：${query}`)
    },
  },
})
