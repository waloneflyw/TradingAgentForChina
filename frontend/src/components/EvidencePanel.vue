<script setup lang="ts">
import { computed } from 'vue'
import type { ReportChunk, ToolCallRecord } from '../types'
import SourceBadge from './SourceBadge.vue'
import { renderMarkdown } from '../utils/markdown'

const props = defineProps<{
  tools: ToolCallRecord[]
  reports: ReportChunk[]
}>()

// 依据层：工具调用时间线 + LLM 报告输出（可折叠）。
function inferSource(name: string): string {
  const n = name.toLowerCase()
  if (/(news|sentiment|social|overview|board|index|hsgt)/.test(n)) return 'akshare'
  if (/(kline|quote|indicator|technical|price)/.test(n)) return 'MySQL/akshare'
  return 'MySQL'
}

const reportHtml = computed(() =>
  props.reports.map((r) => ({ ...r, html: renderMarkdown(r.content) })),
)
</script>

<template>
  <div class="evidence">
    <div v-if="!tools.length && !reports.length" class="empty">
      暂无过程数据。请从实时分析中查看工具调用与报告生成依据。
    </div>

    <!-- 工具调用时间线 -->
    <div v-if="tools.length" class="section">
      <div class="section-title">工具调用（{{ tools.length }}）</div>
      <ol class="timeline">
        <li v-for="(t, i) in tools" :key="i" class="tl-item">
          <div class="tl-dot" :class="t.phase" />
          <div class="tl-body">
            <div class="tl-head">
              <code class="tool-name">{{ t.name }}</code>
              <SourceBadge :source="inferSource(t.name)" />
            </div>
            <div v-if="t.phase === 'call' && t.detail" class="tl-args mono">{{ t.detail }}</div>
            <div v-if="t.phase === 'result'" class="tl-result">返回结果</div>
          </div>
        </li>
      </ol>
    </div>

    <!-- LLM 报告输出 -->
    <div v-if="reports.length" class="section">
      <div class="section-title">分析师报告（{{ reports.length }}）</div>
      <details v-for="(r, i) in reportHtml" :key="i" class="report-item" :open="i === 0">
        <summary>{{ r.analyst }}</summary>
        <div class="markdown report-body" v-html="r.html" />
      </details>
    </div>
  </div>
</template>

<style scoped>
.empty {
  color: var(--text-3);
  text-align: center;
  padding: 40px 0;
}
.section {
  margin-bottom: 20px;
}
.section-title {
  font-weight: 600;
  margin-bottom: 10px;
  color: var(--text);
}
.timeline {
  list-style: none;
  margin: 0;
  padding: 0;
}
.tl-item {
  position: relative;
  padding: 0 0 14px 22px;
  border-left: 2px solid var(--border);
  margin-left: 6px;
}
.tl-item:last-child {
  border-left-color: transparent;
}
.tl-dot {
  position: absolute;
  left: -7px;
  top: 4px;
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background: var(--border-strong);
}
.tl-dot.call {
  background: var(--accent);
}
.tl-dot.result {
  background: var(--node-done);
}
.tl-head {
  display: flex;
  align-items: center;
  gap: 8px;
}
.tool-name {
  background: var(--bg-hover);
  padding: 1px 6px;
  border-radius: 4px;
  font-size: 12px;
}
.tl-args {
  margin-top: 4px;
  font-size: 12px;
  color: var(--text-2);
  word-break: break-all;
}
.tl-result {
  margin-top: 4px;
  font-size: 12px;
  color: var(--text-2);
}
.report-item {
  border: 1px solid var(--border);
  border-radius: 8px;
  margin-bottom: 8px;
  overflow: hidden;
}
.report-item summary {
  padding: 8px 12px;
  cursor: pointer;
  background: var(--bg-hover);
  font-weight: 500;
}
.report-body {
  padding: 10px 14px;
  border-top: 1px solid var(--border);
}
</style>
