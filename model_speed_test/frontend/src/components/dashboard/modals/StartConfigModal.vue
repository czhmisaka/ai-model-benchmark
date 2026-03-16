<template>
  <div class="modal-overlay" :class="{ show: visible }">
    <div class="modal">
      <div class="modal-title">测试启动配置</div>
      <div class="form-group">
        <label class="form-label">测试轮数 (Test Rounds)</label>
        <input type="number" class="form-input" v-model="config.test_rounds" min="1" max="100" />
        <div class="form-hint">每个模型-测试用例组合重复测试的轮数</div>
      </div>
      <div class="form-group">
        <label class="form-label">最大并发数 (Max Concurrent)</label>
        <input type="number" class="form-input" v-model="config.max_concurrent" min="1" max="10" />
        <div class="form-hint">同时运行的模型数量（0表示不限制）</div>
      </div>
      <div class="form-group">
        <label class="form-label">请求间隔 (秒)</label>
        <input type="number" class="form-input" v-model="config.interval" min="0" max="60" step="0.5" />
        <div class="form-hint">每轮测试之间的等待时间</div>
      </div>
      <div class="form-group">
        <label class="form-label">测试名称（可选）</label>
        <input type="text" class="form-input" v-model="config.test_name" placeholder="自动生成" />
        <div class="form-hint">用于标识这次测试，方便历史记录查找</div>
      </div>
      <div class="form-actions">
        <button class="btn btn-secondary" @click="$emit('cancel')">取消</button>
        <button class="btn btn-primary" @click="$emit('confirm')">确认启动</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
interface StartConfig {
  test_rounds: number
  max_concurrent: number
  interval: number
  test_name: string
}

interface Props {
  visible: boolean
  config: StartConfig
}

defineProps<Props>()

defineEmits<{
  cancel: []
  confirm: []
}>()
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
  width: 480px;
  max-width: 90vw;
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

.form-group {
  margin-bottom: 14px;
}

.form-label {
  font-size: 0.7rem;
  color: var(--gray-600);
  margin-bottom: 6px;
  display: block;
}

.form-hint {
  font-size: 0.65rem;
  color: var(--gray-500);
  margin-top: 4px;
}

.form-input {
  width: 100%;
  padding: 10px 14px;
  background: var(--gray-50);
  border: 1px solid var(--gray-200);
  border-radius: 8px;
  color: var(--gray-900);
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.8rem;
  transition: all 0.2s ease;
  box-sizing: border-box;
  
  &::placeholder {
    color: var(--gray-400);
  }
  
  &:focus {
    outline: none;
    border-color: var(--primary);
    background: var(--white);
    box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.1);
  }
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

.btn-primary {
  background: var(--primary);
  color: var(--white);
  border-color: var(--primary);
  
  &:hover:not(:disabled) {
    background: var(--primary-light);
    border-color: var(--primary-light);
    color: var(--white);
  }
}

.btn-secondary {
  &:hover:not(:disabled) {
    background: var(--gray-50);
  }
}
</style>