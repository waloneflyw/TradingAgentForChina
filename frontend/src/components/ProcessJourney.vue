<script setup lang="ts">
import { computed } from 'vue'
import type { NodeState, ToolCallRecord, ReportChunk } from '../types'
import {
  nodesByStage,
  STAGE_LABELS,
  AGENT_TO_REPORT,
  AGENT_PLAN_FIELD,
  toolLabel,
} from '../utils/agents'
import { fmtMs } from '../utils/format'
import { reportGist } from '../utils/markdown'

const props = defineProps<{
  nodes: Record<string, NodeState>
  tools: ToolCallRecord[]
  reports: ReportChunk[]
  reportJson?: Record<string, unknown> | null
}>()

const stages = computed(() => nodesByStage())

function stateOf(name: string): NodeState {
  return props.nodes[name] ?? { status: 'waiting' as const }
}

const STATUS_ICON: Record<string, string> = { waiting: '○', running: '●', done: '✓', failed: '✗' }

// 工具按归属 agent 分组，去重计数（仅 call 阶段；结果归「依据」页）
const toolsByNode = computed(() => {
  const map: Record<string, { label: string; count: number }[]> = {}
  for (const t of props.tools) {
    if (t.phase !== 'call') continue
    const key = t.node || '其他'
    const list = (map[key] ||= [])
    const exist = list.find((x) => x.label === toolLabel(t.name))
    if (exist) exist.count++
    else list.push({ label: toolLabel(t.name), count: 1 })
  }
  return map
})

const reportByLabel = computed(() => {
  const m: Record<string, string> = {}
  for (const r of props.reports) m[r.analyst] = r.content
  return m
})

/** agent 的「精简结论」：分析师取对应报告一句话摘要；经理/交易员/组合经理取 plan 字段。 */
function conclusionOf(name: string): string {
  const label = AGENT_TO_REPORT[name]
  if (label) {
    const content = reportByLabel.value[label]
    return content ? reportGist(content) : ''
  }
  const field = AGENT_PLAN_FIELD[name]
  if (field && props.reportJson) {
    const content = props.reportJson[field]
    return content ? reportGist(String(content)) : ''
  }
  return ''
}
</script>

<template>
  <div class="journey">
    <section v-for="(stage, si) in stages" :key="si" class="stage">
      <div class="stage-head">
        <span class="stage-label">{{ STAGE_LABELS[si] }}</span>
        <span class="stage-rail" />
      </div>

      <div class="agents">
        <div
          v-for="node in stage"
          :key="node.name"
          class="agent"
          :class="`a-${stateOf(node.name).status}`"
        >
          <div class="agent-head">
            <span class="agent-icon">{{ STATUS_ICON[stateOf(node.name).status] }}</span>
            <span class="agent-name">{{ node.label }}</span>
            <span v-if="stateOf(node.name).elapsedMs" class="agent-elapsed mono">
              {{ fmtMs(stateOf(node.name).elapsedMs) }}
            </span>
          </div>

          <!-- 该 agent 调用的数据工具（路程图：做了什么） -->
          <div v-if="toolsByNode[node.name]?.length" class="agent-tools">
            <span
              v-for="t in toolsByNode[node.name]"
              :key="t.label"
              class="tool-chip"
              :title="`调用 ${t.count} 次`"
            >
              {{ t.label }}<span v-if="t.count > 1" class="count">×{{ t.count }}</span>
            </span>
          </div>

          <!-- 精简结论（关键词句） -->
          <div v-if="conclusionOf(node.name)" class="agent-gist">
            <span class="gist-tag">结论</span>
            <span class="gist-text">{{ conclusionOf(node.name) }}</span>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.journey {
  display: flex;
  flex-direction: column;
  gap: 18px;
}
.stage-head {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 10px;
}
.stage-label {
  flex: none;
  font-size: 13px;
  font-weight: 600;
  color: var(--accent);
}
.stage-rail {
  flex: 1;
  height: 1px;
  background: var(--border);
}
.agents {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.agent {
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--bg-card);
  padding: 10px 12px;
}
.agent-head {
  display: flex;
  align-items: center;
  gap: 8px;
}
.agent-icon {
  width: 18px;
  height: 18px;
  border-radius: 50%;
  flex: none;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  color: #fff;
  background: var(--node-wait);
}
.agent-name {
  font-weight: 600;
  font-size: 13px;
}
.agent-elapsed {
  margin-left: auto;
  font-size: 11px;
  color: var(--text-3);
}

/* 状态配色 */
.a-done .agent-icon {
  background: var(--node-done);
}
.a-done {
  border-color: color-mix(in srgb, var(--node-done) 40%, var(--border));
}
.a-running .agent-icon {
  background: var(--node-run);
  animation: pulse 1.2s ease-in-out infinite;
}
.a-running {
  border-color: var(--node-run);
  background: var(--accent-soft);
}
.a-failed .agent-icon {
  background: var(--node-fail);
}
.a-failed {
  border-color: var(--node-fail);
}

.agent-tools {
  margin-top: 8px;
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.tool-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 9px;
  border-radius: 14px;
  border: 1px solid var(--border-strong);
  background: var(--bg-hover);
  font-size: 12px;
  color: var(--text-2);
}
.tool-chip .count {
  color: var(--text-3);
  font-size: 11px;
}
.agent-gist {
  margin-top: 8px;
  display: flex;
  align-items: flex-start;
  gap: 8px;
  font-size: 12px;
  line-height: 1.5;
}
.gist-tag {
  flex: none;
  color: var(--accent);
  font-weight: 600;
  border: 1px solid var(--accent);
  border-radius: 4px;
  padding: 0 5px;
  font-size: 11px;
  line-height: 1.6;
}
.gist-text {
  color: var(--text-2);
}
</style>
