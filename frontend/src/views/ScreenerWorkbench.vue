<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { screenerStructured } from '../api'
import { useChatStore } from '../stores/chat'
import StockTable from '../components/StockTable.vue'
import ComplianceFooter from '../components/ComplianceFooter.vue'
import type { ScreenerRow } from '../types'

const router = useRouter()
const chat = useChatStore()

const form = ref({
  industry: '',
  min_roe: null as number | null,
  max_pe: null as number | null,
  min_growth: null as number | null,
  min_attention: null as number | null,
  max_turnover: null as number | null,
})

const rows = ref<ScreenerRow[]>([])
const loading = ref(false)
const searched = ref(false)
const error = ref('')

function num(v: string): number | null {
  const t = v.trim()
  return t === '' ? null : Number(t)
}

async function run() {
  loading.value = true
  error.value = ''
  try {
    rows.value = await screenerStructured({
      industry: form.value.industry.trim() || undefined,
      min_roe: form.value.min_roe ?? undefined,
      max_pe: form.value.max_pe ?? undefined,
      min_growth: form.value.min_growth ?? undefined,
      min_attention: form.value.min_attention ?? undefined,
      max_turnover: form.value.max_turnover ?? undefined,
      limit: 100,
    })
    searched.value = true
  } catch (e: any) {
    error.value = e?.message || '查询失败'
  } finally {
    loading.value = false
  }
}

function analyze(row: ScreenerRow) {
  chat.sendAnalysis(row.stock_code, row.name)
  router.push('/')
}

const FIELDS = [
  { key: 'industry', label: '行业', ph: '申万一级名，如 电力设备 / 食品饮料', type: 'text' },
  { key: 'min_roe', label: 'ROE ≥ (%)', ph: '如 15', type: 'number' },
  { key: 'max_pe', label: 'PE ≤', ph: '如 30', type: 'number' },
  { key: 'min_growth', label: '净利增速 ≥ (%)', ph: '如 20', type: 'number' },
  { key: 'min_attention', label: '关注指数 ≥', ph: '如 80', type: 'number' },
  { key: 'max_turnover', label: '换手率 ≤ (%)', ph: '如 10', type: 'number' },
] as const
</script>

<template>
  <div class="screener">
    <header class="head">
      <button class="btn" @click="router.push('/')">← 返回对话</button>
      <h1>标签选股</h1>
    </header>

    <div class="body">
      <div class="card form">
        <div class="grid">
          <label v-for="f in FIELDS" :key="f.key" class="field">
            <span class="label">{{ f.label }}</span>
            <input
              v-if="f.type === 'text'"
              v-model="form[f.key as 'industry']"
              class="input"
              :placeholder="f.ph"
              @keydown.enter="run"
            />
            <input
              v-else
              v-model.number="form[f.key as 'min_roe']"
              type="number"
              class="input"
              :placeholder="f.ph"
              @keydown.enter="run"
            />
          </label>
        </div>
        <div class="form-actions">
          <button class="btn btn-primary" :disabled="loading" @click="run">
            {{ loading ? '筛选中…' : '开始初筛' }}
          </button>
          <span class="note">条件可留空；命中按综合得分降序，最多 100 只。</span>
        </div>
      </div>

      <div v-if="error" class="error">⚠️ {{ error }}</div>

      <div v-if="searched" class="result">
        <div class="result-head">命中 {{ rows.length }} 只</div>
        <StockTable :rows="rows" @analyze="analyze" />
      </div>

      <ComplianceFooter />
    </div>
  </div>
</template>

<style scoped>
.screener {
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
.body {
  flex: 1;
  overflow-y: auto;
  padding: 20px 24px;
  max-width: 1100px;
  width: 100%;
  margin: 0 auto;
}
.form {
  padding: 16px 18px;
  margin-bottom: 16px;
}
.grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
}
.field {
  display: flex;
  flex-direction: column;
  gap: 5px;
}
.label {
  font-size: 12px;
  color: var(--text-2);
}
.input {
  padding: 8px 10px;
  border: 1px solid var(--border-strong);
  border-radius: 8px;
  background: var(--bg-elev);
  color: var(--text);
  outline: none;
}
.input:focus {
  border-color: var(--accent);
}
.form-actions {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 14px;
}
.note {
  font-size: 12px;
  color: var(--text-3);
}
.error {
  color: var(--node-fail);
  margin-bottom: 12px;
}
.result-head {
  margin-bottom: 10px;
  font-weight: 600;
}
@media (max-width: 720px) {
  .grid {
    grid-template-columns: repeat(2, 1fr);
  }
}
</style>
