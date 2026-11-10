<script setup lang="ts">
import { computed } from 'vue'
import type { Rating } from '../types'

const props = withDefaults(defineProps<{ rating: Rating; withWeak?: boolean; large?: boolean }>(), {
  withWeak: false,
  large: false,
})

const WEAK: Record<string, string> = {
  买: '相对强烈看多',
  增持: '相对偏多',
  持有: '相对中性',
  减持: '相对偏空',
  卖: '相对强烈看空',
}

const COLOR: Record<string, string> = {
  买: 'var(--rating-buy)',
  增持: 'var(--rating-overweight)',
  持有: 'var(--rating-hold)',
  减持: 'var(--rating-underweight)',
  卖: 'var(--rating-sell)',
}

const color = computed(() => COLOR[props.rating] ?? 'var(--rating-hold)')
const weak = computed(() => WEAK[props.rating] ?? props.rating)
</script>

<template>
  <span class="rating-wrap">
    <span
      class="rating-badge"
      :class="{ large }"
      :style="{ background: color }"
      :title="`${weak} · 不构成投资建议`"
    >
      {{ rating }}
    </span>
    <span v-if="withWeak" class="rating-weak" :style="{ color }">{{ weak }}</span>
  </span>
</template>

<style scoped>
.rating-wrap {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}
.rating-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 40px;
  height: 26px;
  padding: 0 10px;
  border-radius: 6px;
  color: #fff;
  font-weight: 600;
  font-size: 13px;
  line-height: 1;
}
.rating-badge.large {
  min-width: 60px;
  height: 40px;
  font-size: 20px;
  border-radius: 9px;
}
.rating-weak {
  font-size: 12px;
  opacity: 0.85;
}
</style>
