<script setup lang="ts">
// 数据来源徽章（QMT / akshare / MySQL）。后端 tool_result 暂未带 source 字段，
// 由调用方按工具名推断传入；缺省显示「数据层」。
const props = withDefaults(defineProps<{ source?: string }>(), { source: '数据层' })

const TONE: Record<string, string> = {
  akshare: 'var(--accent-soft)',
  MySQL: 'var(--rating-overweight)',
  QMT: 'var(--rating-underweight)',
}

const tone = () => TONE[props.source] ?? 'var(--bg-hover)'
</script>

<template>
  <span class="source-badge" :style="{ background: tone(), color: 'var(--text-2)' }">
    {{ source }}
  </span>
</template>

<style scoped>
.source-badge {
  display: inline-block;
  padding: 1px 8px;
  border-radius: 4px;
  font-size: 11px;
  line-height: 1.7;
  border: 1px solid var(--border);
}
</style>
