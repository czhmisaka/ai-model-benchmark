<template>
  <div class="modal-overlay" :class="{ show: visible }">
    <div class="modal history-modal">
      <div class="modal-title">测试历史记录</div>
      <div class="modal-body">
        <div class="history-list" v-if="historyList.length">
          <div 
            v-for="group in historyList" 
            :key="group.group_id"
            class="history-item"
            @click="$emit('view', group.group_id)"
          >
            <div class="history-info">
              <div class="history-name">{{ group.name || group.group_id }}</div>
              <div class="history-meta">
                {{ formatDate(group.start_time) }} • {{ group.config?.models?.length || 0 }} 模型 × {{ group.config?.test_cases?.length || 0 }} 测试用例 • {{ group.total_rounds || 0 }} 轮
              </div>
            </div>
            <div class="history-stats">
              <div class="history-stat">
                <div class="history-stat-value">{{ group.completed_rounds || 0 }}</div>
                <div class="history-stat-label">完成</div>
              </div>
              <div class="history-stat">
                <div class="history-stat-value" style="color:var(--primary)">{{ group.success_count || 0 }}</div>
                <div class="history-stat-label">成功</div>
              </div>
              <div class="history-stat">
                <div class="history-stat-value" style="color:var(--accent-red)">{{ group.failed_count || 0 }}</div>
                <div class="history-stat-label">失败</div>
              </div>
            </div>
            <div class="history-actions">
              <button class="btn btn-secondary" style="padding:6px 12px;font-size:0.65rem" @click.stop="$emit('delete', group.group_id)">删除</button>
            </div>
          </div>
        </div>
        <div v-else style="color:var(--gray-500);text-align:center;padding:20px;">暂无历史记录</div>
      </div>
      <div class="form-actions">
        <button class="btn btn-secondary" @click="$emit('close')">关闭</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
interface HistoryItem {
  group_id: string
  name?: string
  start_time: string
  config?: {
    models?: string[]
    test_cases?: string[]
  }
  total_rounds?: number
  completed_rounds?: number
  success_count?: number
  failed_count?: number
}

interface Props {
  visible: boolean
  historyList: HistoryItem[]
}

defineProps<Props>()

defineEmits<{
  close: []
  view: [groupId: string]
  delete: [groupId: string]
}>()

function formatDate(dateStr: string): string {
  if (!dateStr) return '--'
  return new Date(dateStr).toLocaleString('zh-CN')
}
</script>

<style lang="scss" scoped>
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.7);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
  opacity: 0;
  visibility: hidden;
  transition: opacity 0.3s ease, visibility 0.3s ease;
  
  &.show {
    opacity: 1;
    visibility: visible;
  }
}

.modal {
  background: var(--white);
  border: 1px solid var(--gray-200);
  border-radius: 16px;
  padding: 24px;
  width: 800px;
  max-width: 95vw;
  max-height: 85vh;
  overflow-y: auto;
  transform: scale(0.95) translateY(10px);
  opacity: 0;
  transition: all 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
  box-shadow: 0 20px 40px rgba(0, 0, 0, 0.15);
  
  .modal-overlay.show & {
    transform: scale(1) translateY(0);
    opacity: 1;
  }
}

.modal-title {
  font-family: 'Space Grotesk', sans-serif;
  font-size: 1rem;
  font-weight: 600;
  color: var(--gray-900);
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--gray-200);
}

.modal-body {
  max-height: calc(85vh - 120px);
  overflow-y: auto;
}

.history-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.history-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px;
  background: var(--gray-100);
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
  border: 1px solid transparent;
  
  &:hover {
    background: var(--gray-200);
    border-color: var(--gray-300);
  }
}

.history-info {
  flex: 1;
}

.history-name {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.8rem;
  color: var(--gray-900);
}

.history-meta {
  font-size: 0.7rem;
  color: var(--gray-500);
  margin-top: 4px;
}

.history-stats {
  display: flex;
  gap: 16px;
}

.history-stat {
  text-align: center;
}

.history-stat-value {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.9rem;
  color: var(--gray-900);
}

.history-stat-label {
  font-size: 0.6rem;
  color: var(--gray-500);
}

.history-actions {
  display: flex;
  gap: 8px;
}

.form-actions {
  display: flex;
  gap: 10px;
  justify-content: flex-end;
  margin-top: 20px;
}

.btn {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.7rem;
  font-weight: 500;
  padding: 8px 16px;
  border-radius: 6px;
  border: 1px solid var(--gray-300);
  background: var(--white);
  color: var(--gray-700);
  cursor: pointer;
  transition: all 0.2s ease;
  letter-spacing: 0.3px;
  min-height: 36px;
  
  &:hover:not(:disabled) {
    border-color: var(--primary);
    color: var(--primary);
    transform: translateY(-1px);
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  }
}

.btn-secondary {
  &:hover:not(:disabled) {
    background: var(--gray-50);
  }
}
</style>