<script setup lang="ts">
import { onMounted } from 'vue'
import { useChatStore } from '../stores/chat'
import { useThemeStore } from '../stores/theme'
import { fmtTime } from '../utils/format'

const chat = useChatStore()
const theme = useThemeStore()

const emit = defineEmits<{ hide: [] }>()

onMounted(() => chat.loadConversations())

function cycleTheme() {
  const order = ['system', 'light', 'dark'] as const
  const next = order[(order.indexOf(theme.mode) + 1) % order.length]
  theme.setMode(next)
}

const themeLabel: Record<string, string> = { system: '跟随系统', light: '亮色', dark: '暗色' }
</script>

<template>
  <aside class="sidebar">
    <div class="brand">
      <span class="logo">研</span><span class="brand-text">A股智研</span>
      <button class="collapse-btn" title="收起侧栏" @click="emit('hide')">«</button>
    </div>

    <button class="btn new-btn" @click="chat.newConversation()">＋ 新建会话</button>

    <nav class="conv-list">
      <button
        v-for="c in chat.conversations"
        :key="c.id"
        class="conv-item"
        :class="{ active: c.id === chat.currentConvId }"
        @click="chat.selectConversation(c.id)"
      >
        <span class="conv-title">{{ c.title || '新会话' }}</span>
        <span class="conv-time">{{ fmtTime(c.updated_at) }}</span>
      </button>
      <div v-if="!chat.conversations.length" class="empty">暂无会话</div>
    </nav>

    <div class="footer">
      <router-link to="/reports" class="btn footer-btn">历史报告</router-link>
      <button class="btn footer-btn" @click="cycleTheme">{{ themeLabel[theme.mode] }}</button>
    </div>
  </aside>
</template>

<style scoped>
.sidebar {
  width: 235px;
  flex: none;
  display: flex;
  flex-direction: column;
  background: var(--bg-elev);
  border-right: 1px solid var(--border);
  padding: 16px 12px;
}
.brand {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 17px;
  font-weight: 700;
  letter-spacing: 0.5px;
  padding: 2px 0 14px;
}
.brand .logo {
  width: 24px;
  height: 24px;
  border-radius: 7px;
  background: var(--ai-grad);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  color: #fff;
  flex: none;
}
.collapse-btn {
  margin-left: auto;
  flex: none;
  border: none;
  background: transparent;
  color: var(--text-3);
  cursor: pointer;
  font-size: 18px;
  line-height: 1;
  padding: 5px 8px;
  border-radius: 6px;
  transition: background 0.15s, color 0.15s;
}
.collapse-btn:hover {
  background: var(--bg-hover);
  color: var(--text);
}
.new-btn {
  width: 100%;
  justify-content: center;
  margin-bottom: 12px;
  font-size: 13px;
  border-color: var(--accent);
  color: var(--accent);
  background: var(--accent-soft);
}
.new-btn:hover {
  background: var(--accent);
  color: #fff;
  border-color: var(--accent);
}
.conv-list {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.conv-item {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 3px;
  padding: 9px 10px 9px 14px;
  border: none;
  border-radius: 8px;
  background: transparent;
  color: var(--text);
  cursor: pointer;
  text-align: left;
}
.conv-item:hover {
  background: var(--bg-hover);
}
.conv-item.active {
  background: var(--accent-soft);
}
.conv-item.active::before {
  content: '';
  position: absolute;
  left: 0;
  top: 50%;
  transform: translateY(-50%);
  width: 3px;
  height: 60%;
  border-radius: 2px;
  background: var(--accent);
}
.conv-item.active .conv-title {
  color: var(--accent);
  font-weight: 600;
}
.conv-title {
  font-size: 13px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 100%;
}
.conv-time {
  font-size: 11px;
  color: var(--text-3);
}
.empty {
  color: var(--text-3);
  font-size: 12px;
  text-align: center;
  padding: 24px 0;
}
.footer {
  border-top: 1px solid var(--border);
  padding-top: 10px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.footer-btn {
  justify-content: center;
}
</style>
