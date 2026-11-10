<script setup lang="ts">
import { onMounted, onBeforeUnmount, ref, watch, shallowRef } from 'vue'
import * as echarts from 'echarts'
import type { KlineBar } from '../types'
import { calcMA, calcMACD, calcRSI, calcBOLL } from '../utils/indicators'

const props = defineProps<{ bars: KlineBar[] }>()

// 红涨绿跌（ECharts 需实际色值，与主题 token 保持一致）
const UP = '#f56c6c'
const UP_DEEP = '#d32f2f'
const DOWN = '#67c23a'
const DOWN_DEEP = '#2e7d32'

type SubIndicator = 'MACD' | 'RSI' | 'BOLL'
const indicator = ref<SubIndicator>('MACD')

const chartEl = ref<HTMLDivElement | null>(null)
const chart = shallowRef<echarts.ECharts | null>(null)
let resizeObs: ResizeObserver | null = null

function buildOption(bars: KlineBar[], sub: SubIndicator): echarts.EChartsOption {
  const dates = bars.map((b) => b.date)
  const closes = bars.map((b) => b.close)
  const kData = bars.map((b) => [b.open, b.close, b.low, b.high])

  const ma5 = calcMA(closes, 5)
  const ma10 = calcMA(closes, 10)
  const ma20 = calcMA(closes, 20)
  const ma60 = calcMA(closes, 60)

  const maSeries = (name: string, data: (number | null)[], color: string) => ({
    name,
    type: 'line' as const,
    data,
    smooth: true,
    symbol: 'none',
    lineStyle: { width: 1, color },
    xAxisIndex: 0,
    yAxisIndex: 0,
  })

  // 子图指标序列
  let subSeries: any[] = []
  let subLegend: string[] = []
  if (sub === 'MACD') {
    const { dif, dea, macd } = calcMACD(closes)
    subLegend = ['DIF', 'DEA', 'MACD']
    subSeries = [
      { name: 'DIF', type: 'line', data: dif.map((v) => (Number.isNaN(v) ? null : v)), symbol: 'none', lineStyle: { width: 1, color: '#f5c542' }, xAxisIndex: 1, yAxisIndex: 1 },
      { name: 'DEA', type: 'line', data: dea.map((v) => (Number.isNaN(v) ? null : v)), symbol: 'none', lineStyle: { width: 1, color: '#3b82f6' }, xAxisIndex: 1, yAxisIndex: 1 },
      {
        name: 'MACD', type: 'bar', xAxisIndex: 1, yAxisIndex: 1,
        data: macd.map((v) => ({ value: v, itemStyle: { color: v >= 0 ? UP : DOWN } })),
      },
    ]
  } else if (sub === 'RSI') {
    const rsi = calcRSI(closes, 14)
    subLegend = ['RSI14']
    subSeries = [
      { name: 'RSI14', type: 'line', data: rsi, symbol: 'none', lineStyle: { width: 1.5, color: '#c084fc' }, xAxisIndex: 1, yAxisIndex: 1 },
    ]
  } else {
    const boll = calcBOLL(closes)
    subLegend = ['BOLL', 'UPPER', 'LOWER']
    const line = (name: string, data: number[], color: string) => ({
      name, type: 'line', data, symbol: 'none', lineStyle: { width: 1, color }, xAxisIndex: 1, yAxisIndex: 1,
    })
    subSeries = [line('BOLL', boll.mid, '#f5c542'), line('UPPER', boll.upper, '#67c23a'), line('LOWER', boll.lower, '#f56c6c')]
  }

  return {
    animation: false,
    axisPointer: { link: [{ xAxisIndex: 'all' }], label: { backgroundColor: '#333' } },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' },
      backgroundColor: 'rgba(20,26,33,0.92)',
      borderColor: 'var(--border)',
      textStyle: { color: '#e6edf3', fontSize: 12 },
    },
    legend: {
      top: 0,
      left: 'center',
      textStyle: { color: '#9aa8b5', fontSize: 11 },
      data: ['MA5', 'MA10', 'MA20', 'MA60', ...subLegend],
    },
    grid: [
      { left: 56, right: 16, top: 30, height: '52%' },
      { left: 56, right: 16, top: '72%', height: '18%' },
    ],
    xAxis: [
      { type: 'category', data: dates, gridIndex: 0, axisLine: { lineStyle: { color: '#3a4554' } }, axisLabel: { color: '#9aa8b5', fontSize: 10 }, boundaryGap: true },
      { type: 'category', data: dates, gridIndex: 1, axisLine: { lineStyle: { color: '#3a4554' } }, axisLabel: { show: false }, boundaryGap: true },
    ],
    yAxis: [
      { scale: true, gridIndex: 0, splitLine: { lineStyle: { color: '#222b35' } }, axisLabel: { color: '#9aa8b5', fontSize: 10 } },
      { scale: true, gridIndex: 1, splitLine: { lineStyle: { color: '#222b35' } }, axisLabel: { color: '#9aa8b5', fontSize: 10 } },
    ],
    dataZoom: [
      { type: 'inside', xAxisIndex: [0, 1], start: 0, end: 100 },
      { type: 'slider', xAxisIndex: [0, 1], top: '92%', height: 16, textStyle: { color: '#9aa8b5' }, borderColor: '#3a4554' },
    ],
    series: [
      {
        name: 'K线',
        type: 'candlestick',
        data: kData,
        xAxisIndex: 0,
        yAxisIndex: 0,
        itemStyle: { color: UP, color0: DOWN, borderColor: UP_DEEP, borderColor0: DOWN_DEEP },
      },
      maSeries('MA5', ma5, '#f5c542'),
      maSeries('MA10', ma10, '#3b82f6'),
      maSeries('MA20', ma20, '#c084fc'),
      maSeries('MA60', ma60, '#f472b6'),
      ...subSeries,
    ],
  }
}

function render() {
  if (!chart.value || !props.bars.length) return
  chart.value.setOption(buildOption(props.bars, indicator.value), true)
}

onMounted(() => {
  if (!chartEl.value) return
  chart.value = echarts.init(chartEl.value)
  render()
  resizeObs = new ResizeObserver(() => chart.value?.resize())
  resizeObs.observe(chartEl.value)
})

watch(() => props.bars, render)
watch(indicator, render)

onBeforeUnmount(() => {
  resizeObs?.disconnect()
  chart.value?.dispose()
  chart.value = null
})
</script>

<template>
  <div class="kline">
    <div class="toolbar">
      <button
        v-for="k in (['MACD', 'RSI', 'BOLL'] as SubIndicator[])"
        :key="k"
        class="seg"
        :class="{ active: indicator === k }"
        @click="indicator = k"
      >
        {{ k }}
      </button>
    </div>
    <div v-if="!bars.length" class="empty">暂无 K 线数据</div>
    <div ref="chartEl" class="chart" />
  </div>
</template>

<style scoped>
.kline {
  position: relative;
  width: 100%;
}
.toolbar {
  display: flex;
  gap: 6px;
  margin-bottom: 8px;
}
.seg {
  padding: 3px 12px;
  border: 1px solid var(--border-strong);
  border-radius: 6px;
  background: var(--bg-card);
  color: var(--text-2);
  cursor: pointer;
  font-size: 12px;
}
.seg.active {
  background: var(--accent);
  border-color: var(--accent);
  color: #fff;
}
.chart {
  width: 100%;
  height: 460px;
}
.empty {
  height: 460px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-3);
}
</style>
