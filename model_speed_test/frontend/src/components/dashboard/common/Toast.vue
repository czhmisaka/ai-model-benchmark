<template>
  <div class="toast" :class="{ show: visible, [type]: true }">{{ message }}</div>
</template>

<script setup lang="ts">
defineProps<{
  message: string
  visible: boolean
  type: string
}>()
</script>

<style lang="scss" scoped>
.toast {
  position: fixed !important;
  bottom: 90px !important;
  left: 50% !important;
  transform: translateX(-50%) translateY(20px);
  background: #111827 !important;
  color: #ffffff !important;
  padding: 8px 16px !important;
  border-radius: 6px !important;
  font-family: 'JetBrains Mono', monospace !important;
  font-size: 12px !important;
  font-weight: 500 !important;
  opacity: 0;
  visibility: hidden;
  transition: all 0.4s cubic-bezier(0.34, 1.56, 0.64, 1);
  z-index: 200;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.25) !important;
  white-space: nowrap;
  height: auto !important;
  max-height: 40px !important;
  max-width: 300px !important;
  min-height: 0 !important;
  line-height: 1.4 !important;
  display: inline-flex !important;
  align-items: center !important;
  gap: 8px !important;
  box-sizing: border-box !important;
  overflow: hidden !important;
  
  &::before {
    content: '';
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: #ffffff !important;
    flex-shrink: 0;
  }
  
  &.show {
    opacity: 1;
    visibility: visible;
    transform: translateX(-50%) translateY(0);
  }
  
  &.success {
    background: linear-gradient(135deg, #f97316 0%, #ea580c 100%);
    color: var(--white);
    
    &::before {
      background: var(--white);
    }
  }
  
  &.error {
    background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
    color: var(--white);
    
    &::before {
      background: var(--white);
    }
  }
}
</style>