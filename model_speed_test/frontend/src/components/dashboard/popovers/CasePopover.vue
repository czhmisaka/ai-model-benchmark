<template>
  <div 
    class="case-popover" 
    :class="{ visible: visible }"
    :style="{ left: x + 'px', top: y + 'px' }"
  >
    <div class="case-popover-title">{{ caseData.name }}</div>
    <div class="case-popover-content" v-if="caseData">
      <div class="case-popover-row" v-if="caseData.id">
        <span class="case-popover-label">ID:</span>
        <span class="case-popover-value">{{ caseData.id }}</span>
      </div>
      <div class="case-popover-row" v-if="caseData.prompt">
        <span class="case-popover-label">Prompt:</span>
        <span class="case-popover-value" style="white-space: pre-wrap; max-height: 100px; overflow-y: auto;">{{ caseData.prompt.substring(0, 200) }}{{ caseData.prompt.length > 200 ? '...' : '' }}</span>
      </div>
      <div class="case-popover-row" v-if="caseData.max_tokens">
        <span class="case-popover-label">Max Tokens:</span>
        <span class="case-popover-value">{{ caseData.max_tokens }}</span>
      </div>
      <div class="case-popover-row" v-if="caseData.temperature">
        <span class="case-popover-label">Temperature:</span>
        <span class="case-popover-value">{{ caseData.temperature }}</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
interface CaseData {
  name?: string
  id?: string
  prompt?: string
  max_tokens?: number
  temperature?: number
}

interface Props {
  visible: boolean
  x: number
  y: number
  caseData: CaseData
}

defineProps<Props>()
</script>

<style lang="scss" scoped>
.case-popover {
  position: fixed;
  z-index: 100;
  background: var(--white);
  border: 1px solid var(--gray-300);
  border-radius: 6px;
  padding: 10px 12px;
  max-width: 300px;
  min-width: 200px;
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

.case-popover-title {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.7rem;
  font-weight: 600;
  color: var(--gray-900);
  margin-bottom: 6px;
  padding-bottom: 4px;
  border-bottom: 1px solid var(--gray-200);
}

.case-popover-content {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.case-popover-row {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.case-popover-label {
  color: var(--gray-500);
  font-size: 0.65rem;
}

.case-popover-value {
  color: var(--gray-900);
  word-break: break-word;
  font-weight: 500;
}
</style>