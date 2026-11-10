<script setup lang="ts">
import { nextTick, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useChatStore } from '../stores/chat'
import ConversationSidebar from '../components/ConversationSidebar.vue'
import MessageBubble from '../components/MessageBubble.vue'
import TaskCard from '../components/TaskCard.vue'
import StockSearchBox from '../components/StockSearchBox.vue'
import ComplianceFooter from '../components/ComplianceFooter.vue'
import type { StockSearchItem } from '../types'

const chat = useChatStore()
const router = useRouter()

const input = ref('')
const showSearch = ref(false)
const listEl = ref<HTMLDivElement | null>(null)
const atBottom = ref(true)
const sidebarOpen = ref(true)

const QUICK = [
  { label: '个股深度分析', icon: '🔎', action: () => (showSearch.value = true) },
  { label: '标签选股', icon: '🏷️', action: () => router.push('/screener') },
  { label: '大盘概览', icon: '📈', action: () => chat.sendMessage('帮我看看今天大盘怎么样') },
  { label: '历史报告', icon: '🗂️', action: () => router.push('/reports') },
]

function scrollBottom(force = false) {
  if (!listEl.value) return
  if (force || atBottom.value) {
    nextTick(() => {
      listEl.value!.scrollTop = listEl.value!.scrollHeight
    })
  }
}

function onScroll() {
  const el = listEl.value
  if (!el) return
  atBottom.value = el.scrollHeight - el.scrollTop - el.clientHeight < 80
}

watch(
  () => chat.messages,
  () => scrollBottom(),
  { deep: true },
)

function onSend() {
  const text = input.value.trim()
  if (!text || chat.streaming) return
  input.value = ''

  // 快捷指令
  if (text.startsWith('/分析')) {
    const code = text.replace('/分析', '').trim()
    if (code) return chat.sendAnalysis(code, code)
  }
  if (text === '/选股') return router.push('/screener')
  if (text === '/报告') return router.push('/reports')
  if (text === '/大盘') return chat.sendMessage('帮我看看今天大盘怎么样')

  chat.sendMessage(text)
}

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    onSend()
  }
}

function onPickStock(item: StockSearchItem) {
  showSearch.value = false
  chat.sendAnalysis(item.stock_code, item.name)
}

onMounted(() => scrollBottom(true))
</script>

<template>
  <div class="layout">
    <ConversationSidebar v-if="sidebarOpen" @hide="sidebarOpen = false" />

    <main class="chat">
      <button
        v-if="!sidebarOpen"
        class="sidebar-toggle"
        title="展开侧栏"
        @click="sidebarOpen = true"
      >
        ☰
      </button>

      <!-- 消息流 -->
      <div ref="listEl" class="msg-list" @scroll="onScroll">
        <div class="msg-col">
          <div v-if="!chat.hasMessages" class="welcome">
            <h1>你好，我是 <span class="grad">A股智研助手</span></h1>
            <p>可以问我个股行情，也可以让我们的分析师团队为您深度分析某只股票，或用标签量化选股。</p>
            <div class="quick-row">
              <button v-for="q in QUICK" :key="q.label" class="btn" @click="q.action">
                <span>{{ q.icon }}</span> {{ q.label }}
              </button>
            </div>
          </div>

          <template v-for="m in chat.messages" :key="m.id">
            <MessageBubble v-if="m.role !== 'task'" :message="m" />
            <TaskCard v-else :task="m.task" />
          </template>
        </div>

        <button v-if="!atBottom" class="back-bottom" @click="scrollBottom(true)">↓ 回到底部</button>
      </div>

      <!-- 输入区 -->
      <div class="input-area">
        <div class="input-wrap">
          <div class="actions">
            <button class="btn chip" @click="showSearch = true">🔎 个股深度分析</button>
            <button class="btn chip" @click="router.push('/screener')">🏷️ 标签选股</button>
          </div>
          <div class="input-card">
            <textarea
              v-model="input"
              class="input"
              rows="1"
              placeholder="输入消息，或使用 /分析 600519 等快捷指令…（Enter 发送 / Shift+Enter 换行）"
              @keydown="onKeydown"
            />
            <button class="btn btn-primary send" :disabled="chat.streaming || !input.trim()" @click="onSend">
              {{ chat.streaming ? '分析中…' : '发送' }}
            </button>
          </div>
        </div>
        <ComplianceFooter />
      </div>
    </main>

    <!-- 个股搜索弹层 -->
    <div v-if="showSearch" class="modal" @click.self="showSearch = false">
      <div class="modal-card card">
        <div class="modal-head">
          <span>选择要分析的股票</span>
          <button class="close" @click="showSearch = false">✕</button>
        </div>
        <StockSearchBox @select="onPickStock" />
      </div>
    </div>
  </div>
</template>

<style scoped>
.layout {
  display: flex;
  height: 100%;
  overflow: hidden;
}
.chat {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  position: relative;
}
.sidebar-toggle {
  position: absolute;
  top: 14px;
  left: 14px;
  z-index: 10;
  width: 34px;
  height: 34px;
  border: 1px solid var(--border);
  border-radius: 9px;
  background: var(--bg-card);
  color: var(--text-2);
  cursor: pointer;
  font-size: 16px;
  box-shadow: var(--shadow);
  transition: border-color 0.15s, color 0.15s;
}
.sidebar-toggle:hover {
  border-color: var(--accent);
  color: var(--accent);
}
.msg-list {
  flex: 1;
  overflow-y: auto;
  padding: 20px 24px;
  position: relative;
}
.msg-col {
  max-width: 1040px;
  margin: 0 auto;
}
.welcome {
  max-width: 560px;
  margin: 8vh auto 0;
  text-align: center;
  color: var(--text-2);
}
.welcome h1 {
  color: var(--text);
  font-size: 24px;
  margin-bottom: 8px;
}
.welcome h1 .grad {
  background: var(--ai-grad);
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
}
.quick-row {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  justify-content: center;
  margin-top: 22px;
}
.quick-row .btn {
  border-color: var(--border);
}
.quick-row .btn:hover {
  border-color: var(--accent);
  color: var(--accent);
}
.back-bottom {
  position: sticky;
  bottom: 12px;
  left: 50%;
  transform: translateX(-50%);
  padding: 6px 14px;
  border-radius: 20px;
  border: 1px solid var(--border-strong);
  background: var(--bg-card);
  color: var(--text);
  cursor: pointer;
  box-shadow: var(--shadow);
}
.input-area {
  background: transparent;
  padding: 4px 24px 18px;
}
.input-wrap {
  max-width: 1040px;
  margin: 0 auto;
}
.actions {
  display: flex;
  gap: 8px;
  margin-bottom: 10px;
}
.chip {
  border-radius: 20px;
  padding: 5px 14px;
  font-size: 13px;
  border-color: var(--border);
  background: var(--bg-card);
}
.chip:hover {
  border-color: var(--accent);
  color: var(--accent);
}
.input-card {
  display: flex;
  align-items: flex-end;
  gap: 10px;
  padding: 10px 10px 10px 16px;
  background: var(--bg-card);
  border: 1px solid var(--border-strong);
  border-radius: 18px;
  box-shadow: var(--shadow);
  transition: border-color 0.15s, box-shadow 0.15s;
}
.input-card:focus-within {
  border-color: var(--accent);
  box-shadow: 0 8px 30px rgba(59, 130, 246, 0.2);
}
.input {
  flex: 1;
  resize: none;
  padding: 7px 0;
  border: none;
  background: transparent;
  color: var(--text);
  font-size: 14px;
  outline: none;
  max-height: 140px;
  line-height: 1.5;
}
.send {
  height: 40px;
  flex: none;
  border-radius: 12px;
  box-shadow: 0 4px 14px var(--accent-soft);
}
.modal {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding-top: 16vh;
  z-index: 100;
}
.modal-card {
  width: 460px;
  max-width: 92vw;
  padding: 16px;
}
.modal-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  font-weight: 600;
}
.close {
  border: none;
  background: transparent;
  color: var(--text-2);
  cursor: pointer;
  font-size: 15px;
}
</style>
