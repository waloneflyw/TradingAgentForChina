<script setup lang="ts">
import { useRouter } from 'vue-router'
import type { TaskRuntime } from '../types'
import RatingBadge from './RatingBadge.vue'
import LiveReports from './LiveReports.vue'

const props = defineProps<{ task: TaskRuntime }>()
const router = useRouter()

const title = () => props.task.title.replace('正在分析', '').trim() || '个股深度分析'

function openWorkbench() {
  if (props.task.taskId) router.push({ name: 'analysis', params: { taskId: props.task.taskId } })
}
</script>

<template>
  <div class="row">
    <div class="avatar">AI</div>
    <div class="report-card card">
      <div class="head">
        <RatingBadge :rating="task.rating ?? '持有'" with-weak />
        <div class="meta">
          <div class="title">{{ title() }}</div>
          <div class="sub">个股深度分析已完成</div>
        </div>
      </div>

      <!-- 各分析师报告（流式期间实时累积，完成后保留可回看） -->
      <LiveReports :reports="task.reports" />

      <div class="actions">
        <button class="btn btn-primary" @click="openWorkbench">展开工作台</button>
      </div>

      <div class="disclaimer">本报告由 AI 自动生成，仅供信息参考，不构成投资建议。</div>
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
.report-card {
  flex: 1;
  min-width: 0;
  max-width: 640px;
  padding: 14px 16px;
  border-left: 3px solid var(--rating-buy);
}
.head {
  display: flex;
  align-items: center;
  gap: 14px;
}
.meta {
  display: flex;
  flex-direction: column;
}
.title {
  font-weight: 600;
  font-size: 15px;
}
.sub {
  font-size: 12px;
  color: var(--text-2);
}
.actions {
  margin-top: 12px;
}
.disclaimer {
  margin-top: 10px;
  font-size: 11px;
  color: var(--text-3);
}
</style>
