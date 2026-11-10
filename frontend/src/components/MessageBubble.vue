<script setup lang="ts">
import { computed } from 'vue'
import { renderMarkdown } from '../utils/markdown'
import type { ChatMessage } from '../types'

// 任务卡片由 TaskCard 单独渲染，这里只处理 user/assistant/system 三种气泡。
type BubbleMessage = Extract<ChatMessage, { role: 'user' | 'assistant' | 'system' }>

const props = defineProps<{ message: BubbleMessage }>()

const html = computed(() => {
  if (props.message.role === 'user') return ''
  return renderMarkdown(props.message.content)
})
</script>

<template>
  <div v-if="message.role === 'user'" class="row user">
    <div class="bubble user-bubble">{{ message.content }}</div>
  </div>

  <div v-else-if="message.role === 'system'" class="row system">
    <span class="sys-text">{{ message.content }}</span>
  </div>

  <div v-else class="row assistant">
    <div class="avatar">AI</div>
    <div class="bubble assistant-bubble">
      <div v-if="message.content" class="markdown" v-html="html" />
      <div v-else class="typing"><span class="dot pulse" /><span class="dot pulse" /><span class="dot pulse" /></div>
    </div>
  </div>
</template>

<style scoped>
.row {
  display: flex;
  margin: 12px 0;
}
.row.user {
  justify-content: flex-end;
}
.row.system {
  justify-content: center;
}
.bubble {
  max-width: 72%;
  padding: 10px 14px;
  border-radius: 12px;
  line-height: 1.6;
}
.user-bubble {
  background: var(--accent);
  color: #fff;
  border-top-right-radius: 4px;
  white-space: pre-wrap;
  word-break: break-word;
}
.assistant-bubble {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-top-left-radius: 4px;
}
.avatar {
  flex: none;
  width: 30px;
  height: 30px;
  margin-right: 10px;
  border-radius: 8px;
  background: var(--ai-grad);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 600;
  box-shadow: 0 2px 8px var(--accent-soft);
}
.sys-text {
  color: var(--text-3);
  font-size: 12px;
}
.typing {
  display: flex;
  gap: 4px;
  padding: 4px 0;
}
.dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--text-3);
}
.dot:nth-child(2) {
  animation-delay: 0.2s;
}
.dot:nth-child(3) {
  animation-delay: 0.4s;
}
</style>
