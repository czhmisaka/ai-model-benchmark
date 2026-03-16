<template>
  <div 
    class="model-popover" 
    :class="{ visible: visible }"
    :style="{ left: x + 'px', top: y + 'px' }"
  >
    <div class="model-popover-title">{{ modelData.display_name || modelData.name }}</div>
    <div class="model-popover-content" v-if="modelData">
      <div class="model-popover-row" v-if="modelData.publisher">
        <span class="model-popover-label">发布者:</span>
        <span class="model-popover-value">{{ modelData.publisher }}</span>
      </div>
      <div class="model-popover-row" v-if="modelData.architecture">
        <span class="model-popover-label">架构:</span>
        <span class="model-popover-value">{{ modelData.architecture }}</span>
      </div>
      <div class="model-popover-row" v-if="modelData.params_string">
        <span class="model-popover-label">参数:</span>
        <span class="model-popover-value">{{ modelData.params_string }}</span>
      </div>
      <div class="model-popover-row" v-if="modelData.quantization">
        <span class="model-popover-label">量化:</span>
        <span class="model-popover-value">{{ modelData.quantization.name }} ({{ modelData.quantization.bits_per_weight }}bit)</span>
      </div>
      <div class="model-popover-row" v-if="modelData.max_context_length">
        <span class="model-popover-label">上下文:</span>
        <span class="model-popover-value">{{ modelData.max_context_length.toLocaleString() }} tokens</span>
      </div>
      <div class="model-popover-row" v-if="modelData.size_bytes">
        <span class="model-popover-label">大小:</span>
        <span class="model-popover-value">{{ formatBytes(modelData.size_bytes) }}</span>
      </div>
      <div class="model-popover-row" v-if="modelData.format">
        <span class="model-popover-label">格式:</span>
        <span class="model-popover-value">{{ modelData.format }}</span>
      </div>
      <div class="model-popover-row" v-if="modelData.key">
        <span class="model-popover-label">Key:</span>
        <span class="model-popover-value" style="font-size: 0.55rem; word-break: break-all;">{{ modelData.key }}</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
interface ModelData {
  display_name?: string
  name?: string
  publisher?: string
  architecture?: string
  params_string?: string
  quantization?: {
    name: string
    bits_per_weight: number
  }
  max_context_length?: number
  size_bytes?: number
  format?: string
  key?: string
}

interface Props {
  visible: boolean
  x: number
  y: number
  modelData: ModelData
}

defineProps<Props>()

function formatBytes(bytes: number): string {
  if (!bytes) return '--'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  let unitIndex = 0
  let size = bytes
  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024
    unitIndex++
  }
  return size.toFixed(1) + ' ' + units[unitIndex]
}
</script>

<style lang="scss" scoped>
.model-popover {
  position: fixed;
  z-index: 100;
  background: var(--white);
  border: 1px solid var(--gray-300);
  border-radius: 6px;
  padding: 10px 12px;
  max-width: 260px;
  min-width: 180px;
  overflow-y: auto;
  font-size: 0.7rem;
  line-height: 1.5;
  color: var(--gray-700);
  box-shadow: 0 4px 16px rgba(0,0,0,0.15);
  display: none;
  pointer-events: none;
  
  &.visible {
    display: block;
  }
}

.model-popover-title {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.7rem;
  font-weight: 600;
  color: var(--gray-900);
  margin-bottom: 6px;
  padding-bottom: 4px;
  border-bottom: 1px solid var(--gray-200);
}

.model-popover-content {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.model-popover-row {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 8px;
}

.model-popover-label {
  color: var(--gray-500);
  flex-shrink: 0;
}

.model-popover-value {
  color: var(--gray-900);
  text-align: right;
  word-break: break-word;
  font-weight: 500;
}
</style>