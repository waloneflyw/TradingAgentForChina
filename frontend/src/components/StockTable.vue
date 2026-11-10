<script setup lang="ts">
import { computed, ref } from 'vue'
import type { ScreenerRow } from '../types'
import { fmtNum, fmtPct, pctClass } from '../utils/format'

const props = defineProps<{ rows: ScreenerRow[] }>()
const emit = defineEmits<{ (e: 'analyze', row: ScreenerRow): void }>()

const sortKey = ref<string>('composite_score')
const sortDir = ref<1 | -1>(-1)

const sorted = computed(() => {
  const arr = [...props.rows]
  const k = sortKey.value as keyof ScreenerRow
  arr.sort((a, b) => {
    const av = a[k] as unknown
    const bv = b[k] as unknown
    const an = typeof av === 'number' ? av : -Infinity
    const bn = typeof bv === 'number' ? bv : -Infinity
    return (an - bn) * sortDir.value
  })
  return arr
})

function toggleSort(key: string) {
  if (sortKey.value === key) sortDir.value = sortDir.value === 1 ? -1 : 1
  else {
    sortKey.value = key
    sortDir.value = -1
  }
}

const sortable = ['latest_price', 'pct_change', 'pe', 'roe', 'net_profit_growth', 'composite_score']
const COLUMNS: { key: string; label: string; num?: boolean }[] = [
  { key: 'stock_code', label: '代码' },
  { key: 'name', label: '名称' },
  { key: 'industry_sw_l1', label: '行业' },
  { key: 'latest_price', label: '现价', num: true },
  { key: 'pct_change', label: '涨跌幅', num: true },
  { key: 'pe', label: 'PE', num: true },
  { key: 'roe', label: 'ROE%', num: true },
  { key: 'net_profit_growth', label: '净利增速%', num: true },
  { key: 'composite_score', label: '综合得分', num: true },
]

function cellVal(row: ScreenerRow, key: string): string {
  const v = row[key as keyof ScreenerRow]
  if (key === 'pct_change') return fmtPct(v as number | null)
  if (typeof v === 'number') return fmtNum(v)
  return (v as string) ?? '—'
}
</script>

<template>
  <div class="table-wrap">
    <table class="stock-table">
      <thead>
        <tr>
          <th v-for="c in COLUMNS" :key="c.key" @click="sortable.includes(c.key) && toggleSort(c.key)">
            {{ c.label }}
            <span v-if="sortKey === c.key" class="sort-arrow">{{ sortDir === -1 ? '↓' : '↑' }}</span>
          </th>
          <th>操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in sorted" :key="row.stock_code">
          <td v-for="c in COLUMNS" :key="c.key" :class="c.key === 'pct_change' ? pctClass(row.pct_change) : ''">
            <span :class="c.key === 'stock_code' ? 'mono' : ''">{{ cellVal(row, c.key) }}</span>
          </td>
          <td>
            <button class="btn analyze" @click="emit('analyze', row)">去分析</button>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="COLUMNS.length + 1" class="empty">暂无候选，请调整筛选条件。</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<style scoped>
.table-wrap {
  overflow-x: auto;
  border: 1px solid var(--border);
  border-radius: 10px;
}
.stock-table {
  border-collapse: collapse;
  width: 100%;
  font-size: 13px;
  min-width: 820px;
}
th,
td {
  padding: 8px 12px;
  text-align: right;
  border-bottom: 1px solid var(--border);
  white-space: nowrap;
}
th {
  background: var(--bg-hover);
  color: var(--text-2);
  font-weight: 500;
  cursor: pointer;
  user-select: none;
  position: sticky;
  top: 0;
}
th:nth-child(1),
th:nth-child(2),
th:nth-child(3),
td:nth-child(1),
td:nth-child(2),
td:nth-child(3) {
  text-align: left;
}
tbody tr:hover {
  background: var(--bg-hover);
}
.sort-arrow {
  font-size: 11px;
  color: var(--accent);
}
.analyze {
  padding: 3px 10px;
  font-size: 12px;
}
.empty {
  text-align: center;
  color: var(--text-3);
  padding: 24px;
}
</style>
