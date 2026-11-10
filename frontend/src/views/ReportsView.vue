<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { listReports } from '../api'
import RatingBadge from '../components/RatingBadge.vue'
import { fmtTime } from '../utils/format'
import type { ReportSummary } from '../types'

const router = useRouter()
const reports = ref<ReportSummary[]>([])
const loading = ref(true)
const stockCode = ref('')
const industry = ref('')

async function load() {
  loading.value = true
  try {
    reports.value = await listReports({
      stock_code: stockCode.value.trim() || undefined,
      industry: industry.value.trim() || undefined,
      limit: 100,
    })
  } finally {
    loading.value = false
  }
}

function open(taskId: string) {
  router.push({ name: 'analysis', params: { taskId } })
}

onMounted(load)
</script>

<template>
  <div class="reports">
    <header class="head">
      <button class="btn" @click="router.push('/')">← 返回对话</button>
      <h1>历史报告</h1>
      <div class="filters">
        <input v-model="stockCode" class="filter" placeholder="股票代码" @keydown.enter="load" />
        <input v-model="industry" class="filter" placeholder="行业（如 食品饮料）" @keydown.enter="load" />
        <button class="btn btn-primary" @click="load">查询</button>
      </div>
    </header>

    <div class="list">
      <div v-if="loading" class="empty">加载中…</div>
      <div v-else-if="!reports.length" class="empty">暂无历史报告。</div>

      <button v-for="r in reports" :key="r.task_id" class="card report-item" @click="open(r.task_id)">
        <div class="left">
          <div class="top">
            <span class="name">{{ r.stock_name || r.stock_code }}</span>
            <span class="code mono">{{ r.stock_code }}</span>
            <span class="industry">{{ r.industry || '—' }}</span>
          </div>
          <div class="summary">{{ r.summary }}</div>
        </div>
        <div class="right">
          <RatingBadge :rating="r.rating" />
          <span class="time">{{ fmtTime(r.create_time) }}</span>
        </div>
      </button>
    </div>
  </div>
</template>

<style scoped>
.reports {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: var(--bg);
}
.head {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 14px 24px;
  border-bottom: 1px solid var(--border);
  background: var(--bg-elev);
}
.head h1 {
  font-size: 18px;
  margin: 0;
}
.filters {
  margin-left: auto;
  display: flex;
  gap: 8px;
}
.filter {
  padding: 7px 10px;
  border: 1px solid var(--border-strong);
  border-radius: 8px;
  background: var(--bg-card);
  color: var(--text);
  outline: none;
}
.list {
  flex: 1;
  overflow-y: auto;
  padding: 20px 24px;
  max-width: 960px;
  width: 100%;
  margin: 0 auto;
}
.report-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  width: 100%;
  padding: 14px 16px;
  margin-bottom: 10px;
  cursor: pointer;
  text-align: left;
  color: var(--text);
}
.report-item:hover {
  border-color: var(--accent);
}
.left {
  flex: 1;
  min-width: 0;
}
.top {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 6px;
}
.name {
  font-weight: 600;
}
.code {
  color: var(--text-2);
  font-size: 12px;
}
.industry {
  font-size: 12px;
  color: var(--text-3);
  background: var(--bg-hover);
  padding: 1px 8px;
  border-radius: 4px;
}
.summary {
  color: var(--text-2);
  font-size: 13px;
  overflow: hidden;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}
.right {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 6px;
}
.time {
  font-size: 11px;
  color: var(--text-3);
}
.empty {
  text-align: center;
  color: var(--text-3);
  padding: 60px 0;
}
</style>
