<script setup lang="ts">
import { ref, watch } from 'vue'
import { searchStocks } from '../api'
import type { StockSearchItem } from '../types'

const props = withDefaults(defineProps<{ placeholder?: string }>(), {
  placeholder: '输入股票名称 / 代码 / 拼音',
})
const emit = defineEmits<{ (e: 'select', item: StockSearchItem): void }>()

const keyword = ref('')
const results = ref<StockSearchItem[]>([])
const open = ref(false)
const loading = ref(false)
let timer: number | undefined

watch(keyword, (v) => {
  window.clearTimeout(timer)
  if (!v.trim()) {
    results.value = []
    open.value = false
    return
  }
  timer = window.setTimeout(async () => {
    loading.value = true
    try {
      results.value = await searchStocks(v.trim(), 10)
      open.value = true
    } catch {
      results.value = []
    } finally {
      loading.value = false
    }
  }, 250)
})

function select(item: StockSearchItem) {
  keyword.value = `${item.name} ${item.stock_code}`
  open.value = false
  emit('select', item)
}
</script>

<template>
  <div class="search-box">
    <input
      v-model="keyword"
      class="input"
      :placeholder="placeholder"
      @focus="results.length && (open = true)"
      @keydown.esc="open = false"
    />
    <span v-if="loading" class="loading">…</span>

    <div v-if="open && results.length" class="dropdown card">
      <button v-for="r in results" :key="r.stock_code" class="item" @click="select(r)">
        <span class="code mono">{{ r.stock_code }}</span>
        <span class="name">{{ r.name }}</span>
        <span class="industry">{{ r.industry_sw_l1 || '—' }}</span>
        <span v-if="r.is_st" class="st">ST</span>
      </button>
    </div>
  </div>
</template>

<style scoped>
.search-box {
  position: relative;
}
.input {
  width: 100%;
  padding: 9px 12px;
  border: 1px solid var(--border-strong);
  border-radius: 8px;
  background: var(--bg-elev);
  color: var(--text);
  font-size: 14px;
  outline: none;
}
.input:focus {
  border-color: var(--accent);
}
.loading {
  position: absolute;
  right: 12px;
  top: 8px;
  color: var(--text-3);
}
.dropdown {
  position: absolute;
  top: 44px;
  left: 0;
  right: 0;
  z-index: 30;
  max-height: 280px;
  overflow-y: auto;
  padding: 4px;
}
.item {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 8px 10px;
  border: none;
  background: transparent;
  color: var(--text);
  cursor: pointer;
  border-radius: 6px;
  text-align: left;
}
.item:hover {
  background: var(--bg-hover);
}
.code {
  font-size: 12px;
  color: var(--text-2);
}
.name {
  font-weight: 500;
}
.industry {
  margin-left: auto;
  font-size: 12px;
  color: var(--text-3);
}
.st {
  color: var(--node-fail);
  font-size: 11px;
  border: 1px solid var(--node-fail);
  border-radius: 3px;
  padding: 0 3px;
}
</style>
