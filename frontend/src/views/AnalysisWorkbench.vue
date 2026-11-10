<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useChatStore } from '../stores/chat'
import { getReport, getKline } from '../api'
import { renderReportMarkdown, reportGist } from '../utils/markdown'
import { AGENT_NODES } from '../utils/agents'
import RatingBadge from '../components/RatingBadge.vue'
import ProcessJourney from '../components/ProcessJourney.vue'
import EvidenceList from '../components/EvidenceList.vue'
import KLineChart from '../components/KLineChart.vue'
import ComplianceFooter from '../components/ComplianceFooter.vue'
import type { FullReport, KlineBar, NodeState, ReportChunk } from '../types'

const route = useRoute()
const router = useRouter()
const chat = useChatStore()

const taskId = route.params.taskId as string
const runtime = computed(() => chat.runtimes[taskId])

const report = ref<FullReport | null>(null)
const bars = ref<KlineBar[]>([])
const loading = ref(true)
const loadError = ref('')

const activeTab = ref<'conclusion' | 'process' | 'evidence'>('conclusion')

function isoDaysAgo(days: number): string {
  const d = new Date()
  d.setDate(d.getDate() - days)
  return d.toISOString().slice(0, 10)
}

onMounted(async () => {
  loading.value = true
  try {
    report.value = await getReport(taskId)
    const code = report.value?.stock_code
    if (code) {
      const end = report.value.analysis_date || isoDaysAgo(0)
      const start = isoDaysAgo(365)
      const k = await getKline(code, start, end)
      bars.value = k.bars
    }
  } catch (e: any) {
    loadError.value = e?.message || '报告加载失败'
  } finally {
    loading.value = false
  }
})

// 进行中的任务默认停「过程」，完成自动切「结论」
watch(
  () => runtime.value?.status,
  (s) => {
    if (s === 'running') activeTab.value = 'process'
    else if (s === 'done') activeTab.value = 'conclusion'
  },
  { immediate: true },
)

// 过程节点：有运行时缓存用缓存，历史报告回退为「全部完成」
const displayNodes = computed<Record<string, NodeState>>(() => {
  const r = runtime.value
  if (r && Object.keys(r.nodes).length) return r.nodes
  const all: Record<string, NodeState> = {}
  for (const a of AGENT_NODES) all[a.name] = { status: 'done' as const }
  return all
})

// 过程/依据层数据：优先运行时缓存；历史报告用 report_json 的四份报告
const evidence = computed<{ tools: any[]; reports: ReportChunk[] }>(() => {
  const r = runtime.value
  if (r) return { tools: r.tools, reports: r.reports }
  const rj = report.value?.report_json
  const list: ReportChunk[] = []
  if (rj) {
    if (rj.market_report) list.push({ analyst: '技术面', content: rj.market_report })
    if (rj.sentiment_report) list.push({ analyst: '情绪面', content: rj.sentiment_report })
    if (rj.news_report) list.push({ analyst: '新闻面', content: rj.news_report })
    if (rj.fundamentals_report) list.push({ analyst: '基本面', content: rj.fundamentals_report })
  }
  return { tools: [], reports: list }
})

// 结论层四份报告：折叠 + 一句话摘要 + 关键字高亮
const reportSections = computed(() =>
  evidence.value.reports.map((r) => ({ analyst: r.analyst, content: r.content, gist: reportGist(r.content) })),
)

const decisionHtml = computed(() =>
  renderReportMarkdown(report.value?.report_json?.final_trade_decision || ''),
)

const TABS = [
  { key: 'conclusion', label: '结论' },
  { key: 'process', label: '过程' },
  { key: 'evidence', label: '依据' },
] as const
</script>

<template>
  <div class="workbench">
    <header class="wb-header">
      <div class="wb-title">
        <span class="name">{{ report?.stock_name || '—' }}</span>
        <span class="code mono">{{ report?.stock_code }}</span>
        <RatingBadge v-if="report" :rating="report.rating" with-weak />
      </div>
      <div class="wb-meta">
        <span v-if="report?.analysis_date" class="date">分析日期 {{ report.analysis_date }}</span>
        <button class="btn" @click="router.push('/')">← 返回对话</button>
      </div>
    </header>

    <nav class="tabs">
      <button
        v-for="t in TABS"
        :key="t.key"
        class="tab"
        :class="{ active: activeTab === t.key }"
        @click="activeTab = t.key"
      >
        {{ t.label }}
      </button>
    </nav>

    <div class="wb-body">
      <div v-if="loading" class="loading">加载报告中…</div>
      <div v-else-if="loadError" class="loading">⚠️ {{ loadError }}</div>

      <!-- 结论：评级 → K线 → 四份报告（折叠） -->
      <div v-else-if="activeTab === 'conclusion'" class="tab-pane">
        <section class="card sec conclusion">
          <RatingBadge :rating="report!.rating" large />
          <div class="concl-sub">评级基于多智能体辩论综合，仅供信息参考。</div>
          <div v-if="decisionHtml" class="markdown report-markdown decision" v-html="decisionHtml" />
        </section>

        <!-- K线 / 技术指标（提到分析师报告上方） -->
        <section class="card sec">
          <h3 class="sec-title">K线 / 技术指标</h3>
          <KLineChart :bars="bars" />
        </section>

        <section v-for="s in reportSections" :key="s.analyst" class="card sec report-sec">
          <details :open="s === reportSections[0]">
            <summary class="rep-summary">
              <span class="rep-name">{{ s.analyst }}分析师报告</span>
              <span class="rep-gist">{{ s.gist }}</span>
            </summary>
            <div class="markdown report-markdown rep-body" v-html="renderReportMarkdown(s.content)" />
          </details>
        </section>

        <ComplianceFooter />
      </div>

      <!-- 过程：分析路程图（各 agent 工具调用 + 精简结论） -->
      <div v-else-if="activeTab === 'process'" class="tab-pane">
        <div class="card sec">
          <ProcessJourney
            :nodes="displayNodes"
            :tools="evidence.tools"
            :reports="evidence.reports"
            :report-json="report?.report_json ?? null"
          />
        </div>
        <div v-if="!runtime" class="hint">历史报告：过程回放不可用，节点显示为已完成（实时分析时才记录耗时与工具调用）。</div>
      </div>

      <!-- 依据：事实依据（真实数据） -->
      <div v-else class="tab-pane">
        <div class="card sec">
          <EvidenceList :tools="evidence.tools" :reports="evidence.reports" />
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.workbench {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: var(--bg);
}
.wb-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 20px;
  border-bottom: 1px solid var(--border);
  background: var(--bg-elev);
}
.wb-title {
  display: flex;
  align-items: center;
  gap: 12px;
}
.name {
  font-size: 18px;
  font-weight: 600;
}
.code {
  color: var(--text-2);
  font-size: 14px;
}
.wb-meta {
  display: flex;
  align-items: center;
  gap: 14px;
}
.date {
  color: var(--text-3);
  font-size: 12px;
}
.tabs {
  display: flex;
  gap: 4px;
  padding: 0 20px;
  border-bottom: 1px solid var(--border);
  background: var(--bg-elev);
}
.tab {
  padding: 10px 20px;
  border: none;
  background: transparent;
  color: var(--text-2);
  cursor: pointer;
  font-size: 14px;
  border-bottom: 2px solid transparent;
}
.tab.active {
  color: var(--accent);
  border-bottom-color: var(--accent);
  font-weight: 600;
}
.wb-body {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
}
.loading {
  text-align: center;
  color: var(--text-3);
  padding: 60px 0;
}
.tab-pane {
  max-width: 960px;
  margin: 0 auto;
}
.sec {
  padding: 16px 18px;
  margin-bottom: 16px;
}
.sec-title {
  margin: 0 0 12px;
  font-size: 15px;
}
.conclusion {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 12px;
}
.concl-sub {
  color: var(--text-3);
  font-size: 12px;
}
.decision {
  border-top: 1px solid var(--border);
  padding-top: 12px;
  width: 100%;
}
.hint {
  color: var(--text-3);
  font-size: 12px;
  margin-top: 8px;
}

/* 折叠报告 */
.report-sec details > summary {
  list-style: none;
  cursor: pointer;
}
.report-sec details > summary::-webkit-details-marker {
  display: none;
}
.rep-summary {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 2px 0;
}
.rep-summary::before {
  content: '▸';
  color: var(--text-3);
  font-size: 12px;
  transition: transform 0.15s;
}
.report-sec details[open] .rep-summary::before {
  transform: rotate(90deg);
}
.rep-name {
  font-weight: 600;
  font-size: 14px;
  flex: none;
}
.rep-gist {
  color: var(--text-3);
  font-size: 12px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.rep-body {
  margin-top: 10px;
  padding-top: 12px;
  border-top: 1px solid var(--border);
}
</style>
