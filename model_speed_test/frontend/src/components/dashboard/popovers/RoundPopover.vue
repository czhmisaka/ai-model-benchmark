<template>
  <div 
    class="round-popover" 
    :class="{ visible: visible, streaming: isStreaming }"
    :style="{ left: x + 'px', top: y + 'px' }"
  >
    <div class="round-popover-header">
      {{ data.name }}
      <span v-if="data.status === 'running'" style="animation: blink 1s infinite;"> ▌</span>
      <span v-else-if="data.status === 'done'"> ✓</span>
      <span v-else-if="data.status === 'error'"> ✗</span>
    </div>
    <div v-if="data.metrics" style="font-size: 0.6rem; color: var(--primary); margin-bottom: 6px;">
      {{ data.metrics }}
    </div>
    <div v-if="data.status === 'pending'" class="round-popover-loading">
      <div class="loading-spinner"></div>等待中...
    </div>
    <div v-else-if="data.output" class="round-popover-content">{{ data.output }}</div>
    <div v-else style="color: var(--gray-500)">无输出</div>
  </div>
</template>

<script setup lang="ts">
interface RoundData {
  name: string
  status: string
  output?: string
  metrics?: string
}

interface Props {
  visible: boolean
  x: number
  y: number
  data: RoundData
  isStreaming?: boolean
}

withDefaults(defineProps<Props>(), {
  isStreaming: false
})
</script>

<style lang="scss" scoped>
.round-popover {
  position: fixed;
  z-index: 100;
  background: var(--white);
  border: 1px solid var(--gray-300);
  border-radius: 6px;
  padding: 10px 12px;
  max-width: 360px;
  max-height: 180px;
  overflow-y: auto;
  font-size: 0.65rem;
  line-height: 1.5;
  color: var(--gray-700);
  white-space: pre-wrap;
  word-break: break-word;
  box-shadow: 0 4px 16px rgba(0,0,0,0.15);
  display: none;
  pointer-events: none;
  
  &.visible {
    display: block;
  }
  
  &.streaming {
    border: 1px dashed var(--accent-purple);
    background: rgba(139, 92, 246, 0.05);
  }
}

.round-popover-header {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.6rem;
  color: var(--gray-900);
  margin-bottom: 6px;
  padding-bottom: 4px;
  border-bottom: 1px solid var(--gray-200);
  display: flex;
  align-items: center;
  gap: 4px;
}

.round-popover-content {
  white-space: pre-wrap;
  word-break: break-word;
  color: var(--gray-600);
}

.round-popover-loading {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--gray-500);
}

.loading-spinner {
  width: 14px;
  height: 14px;
  border: 2px solid var(--gray-600);
  border-top-color: var(--primary);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  flex-shrink: 0;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}
</style>