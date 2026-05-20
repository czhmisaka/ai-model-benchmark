<template>
  <header class="header">
    <div class="logo">
      <button class="fullscreen-btn" @click="$emit('toggle-fullscreen')" title="全屏显示">
        <span class="fullscreen-icon">{{ isFullscreen ? '⤓' : '⤢' }}</span>
      </button>
      Czhmisaka
      <span class="logo-tag">MODEL TEST</span>
    </div>
    <div class="status-row">
      <div class="status-item">
        <span class="status-dot" :class="{ connected: sseConnected }"></span>
        <span class="status-label">SSE</span>
        <span class="status-value">{{ sseStatus }}</span>
      </div>
      <div class="status-item">
        <span class="status-dot" :class="{ running: testRunning }"></span>
        <span class="status-label">TEST</span>
        <span class="status-value">{{ testStatus }}</span>
      </div>
    </div>
    <div class="controls">
      <button class="btn btn-primary" id="startBtn" @click="$emit('start')" :disabled="testRunning">▶ START</button>
      <button class="btn btn-secondary" id="stopBtn" @click="$emit('stop')" :disabled="!testRunning">■ STOP</button>
      <button class="btn btn-secondary" id="clearBtn" @click="$emit('clear')">✕ CLEAR</button>
      <button class="btn btn-secondary" id="historyBtn" @click="$emit('show-history')">☰ HISTORY</button>
      <button class="btn btn-accent" id="aiAnalysisBtn" @click="$emit('ai-analysis')" :disabled="aiAnalysisLoading">🤖 AI 分析</button>
    </div>
  </header>
</template>

<script setup lang="ts">
interface Props {
  isFullscreen: boolean
  sseConnected: boolean
  sseStatus: string
  testRunning: boolean
  testStatus: string
  aiAnalysisLoading: boolean
}

defineProps<Props>()

defineEmits<{
  'toggle-fullscreen': []
  start: []
  stop: []
  clear: []
  'show-history': []
  'ai-analysis': []
}>()
</script>

<style lang="scss" scoped>
.header {
  background: var(--white);
  border-bottom: 1px solid var(--gray-200);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
}

.fullscreen-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  padding: 0;
  border: none;
  background: transparent;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s;
  margin-right: 16px;
  flex-shrink: 0;
  
  &:hover {
    background: var(--gray-200);
  }
  
  .fullscreen-icon {
    font-size: 20px;
    color: var(--gray-600);
  }
  
  &:hover .fullscreen-icon {
    color: var(--gray-900);
  }
}

.logo {
  font-family: 'Space Grotesk', sans-serif;
  font-size: 0.95rem;
  font-weight: 600;
  color: var(--gray-900);
  display: flex;
  align-items: center;
  gap: 8px;
  letter-spacing: -0.02em;
}

.logo-tag {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.55rem;
  color: var(--gray-500);
  border: 1px solid var(--gray-300);
  padding: 2px 6px;
  letter-spacing: 0.05em;
}

.controls {
  display: flex;
  gap: 12px;
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
  
  &:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }
  
  &:hover:not(:disabled) {
    border-color: var(--primary);
    color: var(--primary);
    transform: translateY(-1px);
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  }
  
  &:focus {
    outline: none;
    box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.2);
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

.btn-accent {
  border-color: var(--accent-orange);
  color: var(--accent-orange);
  
  &:hover:not(:disabled) {
    background: rgba(249, 115, 22, 0.08);
    border-color: var(--accent-orange);
    color: var(--accent-orange-dark, #ea580c);
    transform: translateY(-1px);
    box-shadow: 0 2px 8px rgba(249, 115, 22, 0.15);
  }
  
  &:disabled {
    opacity: 0.5;
    cursor: not-allowed;
    animation: pulse 1.5s infinite;
  }
}

.status-row {
  display: flex;
  gap: 20px;
}

.status-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.75rem;
}

.status-dot {
  width: 10px;
  height: 10px;
  min-width: 10px;
  border-radius: 50%;
  background: var(--gray-400);
  transition: all 0.3s;
  
  &.connected {
    background: var(--primary);
    box-shadow: 0 0 8px rgba(37, 99, 235, 0.5);
  }
  
  &.running {
    background: var(--accent-orange);
    box-shadow: 0 0 8px rgba(249, 115, 22, 0.5);
    animation: pulse 1.5s infinite;
  }
}

@keyframes pulse {
  0%, 100% { 
    transform: scale(1);
    opacity: 1;
  }
  50% { 
    transform: scale(1.2);
    opacity: 0.8;
  }
}

.status-label {
  color: var(--gray-400);
}

.status-value {
  color: var(--gray-700);
}
</style>