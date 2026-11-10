<script setup lang="ts">
import { computed } from 'vue'
import type { TaskRuntime } from '../types'
import { AGENT_NODES } from '../utils/agents'
import LiveReports from './LiveReports.vue'
import ReportCard from './ReportCard.vue'

const props = defineProps<{ task: TaskRuntime }>()

// 分析任务：固定 12 节点顺序的迷你流水线 + 完成进度
const pipeline = computed(() => {
  if (props.task.kind !== 'analysis') return []
  return AGENT_NODES.map((a) => ({
    ...a,
    state: props.task.nodes[a.name] ?? { status: 'waiting' as const },
  }))
})

const doneCount = computed(() => pipeline.value.filter((p) => p.state.status === 'done').length)
const totalCount = computed(() => pipeline.value.length || 1)
const progressPct = computed(() => Math.round((doneCount.value / totalCount.value) * 100))

// 实时数据工具调用指示
const activeTool = computed(() => {
  const t = props.task.tools[props.task.tools.length - 1]
  return t && t.phase === 'call' ? t.name : ''
})
const toolCount = computed(() => props.task.tools.filter((t) => t.phase === 'call').length)

const statusColor: Record<string, string> = {
  waiting: 'var(--node-wait)',
  running: 'var(--node-run)',
  done: 'var(--node-done)',
  failed: 'var(--node-fail)',
}
</script>

<template>
  <!-- 完成的分析任务 → 报告卡片 -->
  <ReportCard v-if="task.kind === 'analysis' && task.status === 'done' && task.taskId" :task="task" />

  <!-- 完成的选股任务 → 简洁完成卡（结果见下方回复） -->
  <div v-else-if="task.kind === 'screener' && task.status === 'done'" class="row">
    <div class="avatar">AI</div>
    <div class="task-card card screener-done">
      <div class="head">
        <span class="done-icon">✓</span>
        <span class="title">选股完成</span>
      </div>
      <div class="sub">候选池结果见下方回复，可继续追问或点击「标签选股」查看明细。</div>
    </div>
  </div>

  <!-- 运行中（分析 / 选股）或失败 -->
  <div v-else class="row">
    <div class="avatar">AI</div>
    <div class="task-card card">
      <div class="head">
        <span class="spinner" :class="{ pulse: task.status === 'running' }" />
        <span class="title">{{ task.title }}</span>
        <span v-if="task.status === 'error'" class="status err">失败</span>
        <span v-else-if="task.status === 'running'" class="status">进行中</span>
      </div>

      <div v-if="task.error" class="err-msg">{{ task.error }}</div>

      <!-- 选股：仅提示筛选进度 -->
      <div v-if="task.kind === 'screener' && task.status === 'running'" class="screener-hint">
        正在筛选候选池…
      </div>

      <!-- 分析任务：进度条 + 流水线 -->
      <template v-if="pipeline.length">
        <div class="progress-line">
          <div class="bar" :style="{ width: `${progressPct}%` }" />
        </div>
        <div class="progress-meta">
          <span>节点 {{ doneCount }}/{{ totalCount }}</span>
          <span v-if="activeTool" class="active-tool mono">正在调用 {{ activeTool }} …</span>
          <span v-else-if="toolCount" class="tool-count">已调用 {{ toolCount }} 个数据工具</span>
        </div>

        <div class="pipeline">
          <div v-for="p in pipeline" :key="p.name" class="agent-chip">
            <span
              class="dot"
              :class="{ pulse: p.state.status === 'running' }"
              :style="{ background: statusColor[p.state.status] }"
            />
            <span class="chip-label" :class="{ dim: p.state.status === 'waiting' }">{{ p.label }}</span>
          </div>
        </div>
      </template>

      <!-- 实时流式报告（各分析师结果） -->
      <LiveReports :reports="task.reports" />
    </div>
  </div>
</template>

<style scoped>
.row {
  display: flex;
  margin: 12px 0;
  align-items: flex-start;
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
.task-card {
  flex: 1;
  min-width: 0;
  max-width: 640px;
  padding: 12px 14px;
  border-left: 3px solid var(--accent);
}
.head {
  display: flex;
  align-items: center;
  gap: 10px;
}
.spinner {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  border: 2px solid var(--accent);
  border-top-color: transparent;
  animation: spin 0.8s linear infinite;
}
@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
.title {
  font-weight: 600;
}
.status {
  margin-left: auto;
  font-size: 12px;
  color: var(--text-2);
}
.status.err {
  color: var(--node-fail);
}
.err-msg {
  margin-top: 8px;
  color: var(--node-fail);
  font-size: 13px;
}
.screener-hint {
  margin-top: 8px;
  font-size: 12px;
  color: var(--text-3);
}
.screener-done .done-icon {
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: var(--node-done);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
}
.screener-done .sub {
  margin-top: 6px;
  font-size: 12px;
  color: var(--text-2);
}
.progress-line {
  margin-top: 12px;
  height: 6px;
  border-radius: 3px;
  background: var(--bg-hover);
  overflow: hidden;
}
.bar {
  height: 100%;
  background: var(--accent);
  border-radius: 3px;
  transition: width 0.4s ease;
}
.progress-meta {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-top: 6px;
  font-size: 12px;
  color: var(--text-2);
}
.active-tool {
  color: var(--accent);
}
.tool-count {
  color: var(--text-3);
}
.pipeline {
  margin-top: 10px;
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.agent-chip {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 3px 9px;
  border: 1px solid var(--border);
  border-radius: 20px;
  background: var(--bg-elev);
}
.dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
}
.chip-label {
  font-size: 12px;
  color: var(--text-2);
}
.chip-label.dim {
  color: var(--text-3);
}
</style>
