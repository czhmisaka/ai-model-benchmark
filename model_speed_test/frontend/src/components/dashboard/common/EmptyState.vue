<template>
  <div class="empty-tasks">
    <div class="empty-icon">{{ icon }}</div>
    <div class="empty-text">{{ title }}</div>
    <div class="empty-hint" v-if="hint">{{ hint }}</div>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  icon?: string
  title: string
  hint?: string
}>()
</script>

<style lang="scss" scoped>
.empty-tasks {
  grid-column: 1 / -1;
  min-height: calc(100vh - 250px);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: var(--gray-400);
  font-size: 0.9rem;
  gap: 12px;
  padding: 40px;
  
  .empty-icon {
    font-size: 64px;
    opacity: 0.4;
  }
  
  .empty-text {
    font-family: 'JetBrains Mono', monospace;
    font-size: 1rem;
    color: var(--gray-500);
  }
  
  .empty-hint {
    font-size: 0.8rem;
    color: var(--gray-400);
    margin-top: 4px;
  }
}
</style>