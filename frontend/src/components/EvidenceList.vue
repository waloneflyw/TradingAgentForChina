<script setup lang="ts">
import { computed } from 'vue'
import type { ToolCallRecord, ReportChunk } from '../types'
import { toolLabel, toolSource, AGENT_TO_REPORT } from '../utils/agents'
import SourceBadge from './SourceBadge.vue'
import { renderReportMarkdown } from '../utils/markdown'

const props = defineProps<{
  tools: ToolCallRecord[]
  reports: ReportChunk[]
}>()

// 事实依据 = 工具 result 阶段返回的真实数据，按归属分析师分组
const factsByNode = computed(() => {
  const map: Record<string, { label: string; source: string; detail: string }[]> = {}
  for (const t of props.tools) {
    if (t.phase !== 'result' || !t.detail) continue
    const key = t.node || '其他'
    ;(map[key] ||= []).push({ label: toolLabel(t.name), source: toolSource(t.name), detail: t.detail })
  }
  return map
})

const orderedNodes = computed(() => Object.keys(factsByNode.value))
const hasFacts = computed(() => orderedNodes.value.length > 0)

const nodeTitle = (name: string) =>
  AGENT_TO_REPORT[name] ? `${AGENT_TO_REPORT[name]}分析师` : name

const reportHtml = computed(() =>
  props.reports.map((r) => ({ ...r, html: renderReportMarkdown(r.content) })),
)
</script>

<template>
  <div class="evidence">
    <div v-if="!hasFacts" class="empty">
      历史报告无过程数据：以下以四份分析师报告原文作为结论依据。
    </div>

    <!-- 事实依据：真实数据按分析师分组 -->
    <div v-for="node in orderedNodes" :key="node" class="group">
      <div class="group-head">
        <span class="group-title">{{ nodeTitle(node) }} · 事实依据</span>
        <span class="group-count">{{ factsByNode[node].length }} 条</span>
      </div>
      <details v-for="(f, i) in factsByNode[node]" :key="i" class="fact" :open="i === 0">
        <summary>
          <span class="fact-label">{{ f.label }}</span>
          <SourceBadge :source="f.source" />
        </summary>
        <pre class="fact-detail">{{ f.detail }}</pre>
      </details>
    </div>

    <!-- 分析师报告原文（综合依据，折叠兜底） -->
    <div v-if="reportHtml.length" class="group">
      <div class="group-head">
        <span class="group-title">分析师报告原文</span>
        <span class="group-count">{{ reportHtml.length }} 份</span>
      </div>
      <details
        v-for="(r, i) in reportHtml"
        :key="r.analyst"
        class="fact"
        :open="!hasFacts && i === 0"
      >
        <summary><span class="fact-label">{{ r.analyst }}分析师</span></summary>
        <div class="markdown report-markdown fact-body" v-html="r.html" />
      </details>
    </div>
  </div>
</template>

<style scoped>
.evidence {
  display: flex;
  flex-direction: column;
  gap: 20px;
}
.empty {
  color: var(--text-3);
  text-align: center;
  padding: 24px 0;
  font-size: 13px;
}
.group-head {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 8px;
}
.group-title {
  font-weight: 600;
  font-size: 14px;
}
.group-count {
  font-size: 12px;
  color: var(--text-3);
}
.fact {
  border: 1px solid var(--border);
  border-radius: 8px;
  margin-bottom: 8px;
  overflow: hidden;
  background: var(--bg-card);
}
.fact summary {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  cursor: pointer;
  background: var(--bg-hover);
  user-select: none;
}
.fact-label {
  font-weight: 500;
  font-size: 13px;
}
.fact-detail {
  margin: 0;
  padding: 10px 14px;
  border-top: 1px solid var(--border);
  font-size: 12px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
  color: var(--text-2);
  max-height: 240px;
  overflow-y: auto;
  font-family: 'SF Mono', 'JetBrains Mono', Consolas, 'Courier New', monospace;
}
.fact-body {
  padding: 10px 14px;
  border-top: 1px solid var(--border);
}
</style>
