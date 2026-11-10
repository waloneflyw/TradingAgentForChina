<script setup lang="ts">
import { ref, watch } from 'vue'
import type { ReportChunk } from '../types'
import { renderMarkdown } from '../utils/markdown'

const props = defineProps<{ reports: ReportChunk[] }>()

// 新报告到达时自动展开最新一份，旧报告收起（点击可回看）
const openIndex = ref(-1)
watch(
  () => props.reports.length,
  (n) => {
    if (n) openIndex.value = n - 1
  },
)

function toggle(i: number) {
  openIndex.value = openIndex.value === i ? -1 : i
}
</script>

<template>
  <div v-if="reports.length" class="live-reports">
    <div v-for="(r, i) in reports" :key="r.analyst" class="report">
      <button class="report-head" @click="toggle(i)">
        <span class="chev">{{ openIndex === i ? '▾' : '▸' }}</span>
        <span class="analyst">{{ r.analyst }}分析师</span>
        <span class="ok">✓</span>
      </button>
      <div v-if="openIndex === i" class="markdown report-body" v-html="renderMarkdown(r.content)" />
    </div>
  </div>
</template>

<style scoped>
.live-reports {
  margin-top: 10px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.report {
  border: 1px solid var(--border);
  border-radius: 8px;
  overflow: hidden;
}
.report-head {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 7px 12px;
  border: none;
  background: var(--bg-hover);
  color: var(--text);
  cursor: pointer;
  font-size: 13px;
  text-align: left;
}
.report-head:hover {
  background: var(--bg-elev);
}
.chev {
  color: var(--text-3);
  font-size: 11px;
}
.analyst {
  font-weight: 500;
}
.ok {
  margin-left: auto;
  color: var(--node-done);
  font-size: 12px;
}
.report-body {
  padding: 10px 14px;
  border-top: 1px solid var(--border);
  max-height: 340px;
  overflow-y: auto;
}
</style>
