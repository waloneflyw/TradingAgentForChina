<script setup lang="ts">
import { computed } from 'vue'
import type { NodeState } from '../types'
import { nodesByStage, STAGE_LABELS } from '../utils/agents'
import { fmtMs } from '../utils/format'

const props = defineProps<{ nodes: Record<string, NodeState> }>()
const emit = defineEmits<{ (e: 'select', name: string): void }>()

const stages = computed(() => nodesByStage())

function stateOf(name: string): NodeState {
  return props.nodes[name] ?? { status: 'waiting' as const }
}

const ICON: Record<string, string> = {
  waiting: '',
  running: '',
  done: '✓',
  failed: '✗',
}
</script>

<template>
  <div class="pipeline">
    <div v-for="(stage, si) in stages" :key="si" class="stage">
      <div class="stage-label">{{ STAGE_LABELS[si] }}</div>
      <div class="nodes">
        <button
          v-for="node in stage"
          :key="node.name"
          class="node"
          :class="`s-${stateOf(node.name).status}`"
          @click="emit('select', node.name)"
        >
          <span class="node-icon">{{ ICON[stateOf(node.name).status] }}</span>
          <span class="node-body">
            <span class="node-name">{{ node.label }}</span>
            <span v-if="stateOf(node.name).elapsedMs" class="node-elapsed">
              {{ fmtMs(stateOf(node.name).elapsedMs) }}
            </span>
          </span>
        </button>
      </div>
    </div>

    <!-- 阶段间箭头（自绘） -->
    <svg v-for="i in 3" :key="i" class="arrow" :style="{ left: `${i * 25}%` }" viewBox="0 0 24 24">
      <line x1="2" y1="12" x2="20" y2="12" :stroke="'var(--border-strong)'" stroke-width="1.5" />
      <polyline points="14,6 20,12 14,18" fill="none" :stroke="'var(--border-strong)'" stroke-width="1.5" />
    </svg>
  </div>
</template>

<style scoped>
.pipeline {
  position: relative;
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 20px;
  padding: 8px 4px;
}
.arrow {
  position: absolute;
  top: 50%;
  width: 20px;
  height: 20px;
  transform: translate(-50%, -50%);
}
.stage-label {
  text-align: center;
  font-size: 12px;
  color: var(--text-2);
  margin-bottom: 10px;
  white-space: nowrap;
}
.nodes {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.node {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  border-radius: 8px;
  border: 1px solid var(--border);
  background: var(--bg-card);
  cursor: pointer;
  text-align: left;
  transition: border-color 0.15s, background 0.15s;
}
.node:hover {
  border-color: var(--accent);
}
.node-icon {
  width: 18px;
  height: 18px;
  border-radius: 50%;
  flex: none;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  color: #fff;
}
.node-body {
  display: flex;
  flex-direction: column;
  line-height: 1.3;
}
.node-name {
  font-size: 13px;
  color: var(--text);
}
.node-elapsed {
  font-size: 11px;
  color: var(--text-3);
}

/* 状态配色 */
.s-waiting .node-icon {
  background: var(--node-wait);
}
.s-waiting .node-name {
  color: var(--text-3);
}
.s-running {
  border-color: var(--node-run);
  background: var(--accent-soft);
}
.s-running .node-icon {
  background: var(--node-run);
}
.s-running .node-icon.pulse,
.s-running .node-icon {
  animation: pulse 1.2s ease-in-out infinite;
}
.s-done .node-icon {
  background: var(--node-done);
}
.s-done {
  border-color: var(--node-done);
}
.s-failed .node-icon {
  background: var(--node-fail);
}
.s-failed {
  border-color: var(--node-fail);
}

@media (max-width: 720px) {
  .pipeline {
    grid-template-columns: repeat(2, 1fr);
  }
  .arrow {
    display: none;
  }
}
</style>
