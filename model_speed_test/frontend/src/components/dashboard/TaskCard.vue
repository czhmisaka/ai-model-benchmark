<template>
  <div 
    class="task-card"
    :class="[task.status, { dragging: isDragging }]"
    :style="cardStyle"
    @click="$emit('click', taskId)"
    @mousedown="$emit('drag-start', $event, taskId)"
  >
    <!-- 卡片尺寸调整手柄 -->
    <div class="card-resize-handle" @mousedown.stop="$emit('resize-start', $event, taskId)"></div>
    
    <div class="task-header">
      <div class="task-info">
        <div class="task-model">{{ task.model_name }}</div>
        <div class="task-case">{{ task.case_name }}</div>
      </div>
      <div class="task-actions">
        <button 
          v-if="task.status === 'running'" 
          class="task-action-btn stop" 
          @click.stop="$emit('stop', taskId)"
          title="停止此任务"
        >■</button>
        <button 
          v-if="task.status === 'done' || task.status === 'error'" 
          class="task-action-btn retry" 
          @click.stop="$emit('retry', taskId)"
          title="重试此任务"
        >↻</button>
        <span class="task-status" :class="task.status">
          {{ runningCount > 0 ? '⟳' : task.status === 'done' ? '✓' : '!' }} {{ doneCount }}/{{ task.total_rounds || 0 }}
        </span>
      </div>
    </div>
    
    <div class="task-progress">
      <div class="task-progress-bar">
        <div class="task-progress-fill" :style="{ width: task.progress + '%' }"></div>
      </div>
      <div class="task-progress-text">
        <span>{{ task.current_round || 0 }}/{{ task.total_rounds || 0 }}</span>
        <span>{{ task.progress }}%</span>
      </div>
    </div>
    
    <div class="task-content">
      <div class="task-io">
        <div class="task-io-header">轮次 Rounds - 点击查看详情</div>
        <div class="round-matrix" :style="{ gridTemplateColumns: `repeat(${gridColumns}, 1fr)` }">
          <div 
            v-for="(subTask, subId) in task.sub_tasks" 
            :key="subId"
            class="round-btn"
            :class="subTask.status"
            :style="{ fontSize: fontSize }"
            @mouseenter="$emit('round-hover', $event, taskId, subId, subTask)"
            @mouseleave="$emit('round-leave')"
          >
            {{ getRoundStatusIcon(subTask.status, getSubTaskIndex(subId) + 1) }}
          </div>
        </div>
      </div>
    </div>
    
    <div class="task-metrics">
      <div class="task-metric">
        <div class="task-metric-value">{{ doneCount }}</div>
        <div class="task-metric-label">完成</div>
      </div>
      <div class="task-metric">
        <div class="task-metric-value">{{ runningCount }}</div>
        <div class="task-metric-label">进行中</div>
      </div>
      <div class="task-metric">
        <div class="task-metric-value">{{ errorCount }}</div>
        <div class="task-metric-label">错误</div>
      </div>
      <div class="task-metric">
        <div class="task-metric-value">{{ task.total_rounds || 0 }}</div>
        <div class="task-metric-label">总计</div>
      </div>
    </div>
    
    <!-- 卡片内的汇总统计（始终显示） -->
    <div class="task-result" :class="{ visible: task.status === 'done' }">
      <div class="task-result-title">平均数据</div>
      <div class="task-result-grid">
        <div class="task-result-item">
          <div class="task-result-value">{{ task.avgTtft || '--' }}</div>
          <div class="task-result-label">TTFT(s)</div>
        </div>
        <div class="task-result-item">
          <div class="task-result-value">{{ task.avgTpft || '--' }}</div>
          <div class="task-result-label">TPFT(s)</div>
        </div>
        <div class="task-result-item">
          <div class="task-result-value">{{ task.avgSpeed || '--' }}</div>
          <div class="task-result-label">速度/s</div>
        </div>
        <div class="task-result-item">
          <div class="task-result-value">{{ task.avgTokens || '--' }}</div>
          <div class="task-result-label">Tokens</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

interface SubTask {
  name: string
  output: string
  status: string
  metrics: any
}

interface Task {
  model_name: string
  case_name: string
  progress: number
  status: string
  current_round: number
  total_rounds: number
  sub_tasks: Record<string, SubTask>
  avgTtft?: string
  avgTpft?: string
  avgTokens?: string
  avgSpeed?: string
}

interface Props {
  taskId: string
  task: Task
  isDragging?: boolean
  width?: number
  height?: number
}

const props = withDefaults(defineProps<Props>(), {
  isDragging: false,
  width: 320,
  height: 180
})

defineEmits<{
  click: [taskId: string]
  'drag-start': [event: MouseEvent, taskId: string]
  'resize-start': [event: MouseEvent, taskId: string]
  'round-hover': [event: MouseEvent, taskId: string, subId: string, subTask: SubTask]
  'round-leave': []
  stop: [taskId: string]
  retry: [taskId: string]
}>()

const doneCount = computed(() => 
  Object.values(props.task.sub_tasks || {}).filter(t => t.status === 'done').length
)

const runningCount = computed(() => 
  Object.values(props.task.sub_tasks || {}).filter(t => t.status === 'running').length
)

const errorCount = computed(() => 
  Object.values(props.task.sub_tasks || {}).filter(t => t.status === 'error').length
)

const gridColumns = computed(() => {
  const totalRounds = props.task.total_rounds || 0
  if (totalRounds <= 10) return 7
  if (totalRounds <= 50) {
    return Math.round(7 + (totalRounds - 10) * (20 - 7) / (50 - 10))
  }
  return Math.round(20 + (Math.min(totalRounds, 100) - 50) * (30 - 20) / (100 - 50))
})

const fontSize = computed(() => {
  const totalRounds = props.task.total_rounds || 0
  if (totalRounds <= 10) return '0.6rem'
  if (totalRounds <= 20) return '0.55rem'
  if (totalRounds <= 30) return '0.5rem'
  if (totalRounds <= 50) return '0.45rem'
  return '0.4rem'
})

const cardStyle = computed(() => {
  const style: Record<string, string> = {}
  if (props.width && props.width !== 320) {
    style.width = props.width + 'px'
  }
  if (props.height && props.height !== 180) {
    style.minHeight = props.height + 'px'
  }
  return style
})

function getSubTaskIndex(subId: string): number {
  const keys = Object.keys(props.task.sub_tasks)
  return keys.indexOf(subId)
}

function getRoundStatusIcon(status: string, roundNum: number): string {
  if (status === 'done') return '✓'
  if (status === 'error') return '✗'
  if (status === 'running') return '⟳'
  return String(roundNum)
}
</script>

<style lang="scss" scoped>
.task-card {
  background: var(--white);
  border: 1px solid var(--gray-200);
  border-radius: 12px;
  padding: 12px;
  display: flex;
  flex-direction: column;
  align-items: stretch;
  min-height: 180px;
  height: auto;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  overflow: visible;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
  flex-shrink: 0;
  cursor: pointer;
  
  &:hover {
    border-color: var(--primary);
    box-shadow: 0 4px 12px rgba(37, 99, 235, 0.15);
    transform: translateY(-2px);
  }
  
  &.done .task-status {
    background: var(--gray-200);
    color: var(--gray-600);
  }
  
  &.error .task-status {
    background: var(--accent-red);
    color: var(--white);
  }
  
  &.stopped .task-status {
    background: var(--gray-500);
    color: var(--white);
  }
  
  &.stopped .task-progress-fill {
    background: var(--gray-500);
  }
  
  &.dragging {
    opacity: 0.5;
    transform: scale(0.95);
  }
}

.card-resize-handle {
  position: absolute;
  right: 0;
  bottom: 0;
  width: 16px;
  height: 16px;
  cursor: nwse-resize;
  
  &::after {
    content: '';
    position: absolute;
    right: 4px;
    bottom: 4px;
    width: 8px;
    height: 8px;
    border-right: 2px solid var(--gray-400);
    border-bottom: 2px solid var(--gray-400);
  }
}

.task-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 8px;
}

.task-info {
  flex: 1;
}

.task-model {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.65rem;
  font-weight: 600;
  color: var(--gray-900);
  margin-bottom: 2px;
}

.task-case {
  font-family: 'Space Grotesk', sans-serif;
  font-size: 0.75rem;
  font-weight: 500;
  color: var(--gray-700);
}

.task-actions {
  display: flex;
  align-items: center;
  gap: 6px;
}

.task-action-btn {
  width: 22px;
  height: 22px;
  min-width: 22px;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.7rem;
  transition: all 0.2s ease;
  
  &.stop {
    background: rgba(239, 68, 68, 0.15);
    color: var(--accent-red);
    
    &:hover {
      background: var(--accent-red);
      color: white;
    }
  }
  
  &.retry {
    background: rgba(59, 130, 246, 0.15);
    color: var(--primary);
    
    &:hover {
      background: var(--primary);
      color: white;
    }
  }
}

.task-status {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.6rem;
  padding: 3px 8px;
  border-radius: 10px;
  
  &.running {
    background: var(--accent-orange);
    color: var(--white);
  }
  
  &.done {
    background: var(--gray-600);
    color: var(--gray-300);
  }
  
  &.error {
    background: var(--accent-red);
    color: var(--white);
  }
}

.task-progress {
  margin-bottom: 8px;
}

.task-progress-bar {
  height: 8px;
  background: var(--gray-200);
  border-radius: 4px;
  overflow: hidden;
  position: relative;
}

.task-progress-fill {
  height: 100%;
  background: var(--primary);
  border-radius: 4px;
  transition: width 0.4s cubic-bezier(0.4, 0, 0.2, 1);
  position: relative;
  box-shadow: 
    0 0 10px rgba(37, 99, 235, 0.5),
    0 0 20px rgba(37, 99, 235, 0.3),
    inset 0 1px 0 rgba(255, 255, 255, 0.3);
  
  &::after {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 50%;
    background: linear-gradient(
      to bottom,
      rgba(255, 255, 255, 0.25),
      transparent
    );
    border-radius: 4px 4px 0 0;
  }
}

.task-progress-text {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--gray-600);
  margin-top: 6px;
  display: flex;
  justify-content: space-between;
}

.task-content {
  display: flex;
  flex-direction: column;
  overflow: visible;
  width: 100%;
  min-height: 30px;
}

.task-io {
  display: block;
  width: 100%;
  overflow: visible;
}

.task-io-header {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.55rem;
  color: var(--gray-500);
  text-transform: uppercase;
  margin-bottom: 3px;
}

.round-matrix {
  display: flex;
  flex-wrap: wrap;
  gap: 3px;
  overflow: visible;
  width: auto;
  min-width: 100%;
}

.round-btn {
  width: auto;
  min-width: 18px;
  height: 18px;
  padding: 0 4px;
  border-radius: 3px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.5rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s;
  background: var(--gray-200);
  color: var(--gray-500);
  border: none;
  
  &.pending {
    background: var(--gray-100);
    color: var(--gray-400);
    
    &:hover {
      background: var(--gray-300);
    }
  }
  
  &.running {
    border-radius: 50%;
    background: var(--accent-orange);
    color: var(--white);
    animation: breathe-pulse 1.5s ease-in-out infinite;
    
    &:hover {
      background: var(--primary-dark);
    }
  }
  
  &.done {
    background: var(--gray-900);
    color: var(--white);
    
    &:hover {
      transform: scale(1.1);
    }
  }
  
  &.error {
    background: var(--white);
    border: 2px solid var(--accent-red);
    color: var(--accent-red);
    font-size: 0.85rem;
    font-weight: 700;
    line-height: 1;
  }
}

@keyframes breathe-pulse {
  0% {
    transform: scale(1);
    box-shadow: 0 0 0 0 rgba(249, 115, 22, 0.4);
  }
  50% {
    transform: scale(1.15);
    box-shadow: 0 0 0 6px rgba(249, 115, 22, 0);
  }
  100% {
    transform: scale(1);
    box-shadow: 0 0 0 0 rgba(249, 115, 22, 0);
  }
}

.task-metrics {
  display: flex;
  gap: 8px;
  margin-top: auto;
  padding-top: 6px;
  border-top: 1px solid var(--gray-100);
}

.task-metric {
  flex: 1;
  text-align: center;
}

.task-metric-value {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--gray-900);
}

.task-metric-label {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.55rem;
  color: var(--gray-500);
  margin-top: 2px;
}

.task-result {
  display: none;
  margin-top: 8px;
  padding: 12px;
  background: linear-gradient(135deg, #fff7ed 0%, #ffedd5 100%);
  border-radius: 8px;
  border: 2px solid #fdba74;
  box-shadow: 0 4px 12px rgba(249, 115, 22, 0.15);
  
  &.visible {
    display: block;
  }
}

.task-result-title {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.65rem;
  color: #1f2937;
  margin-bottom: 10px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  font-weight: 100;
}

.task-result-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
}

.task-result-item {
  text-align: center;
  padding: 8px;
  background: rgba(255, 255, 255, 0.5);
  border-radius: 6px;
  transition: all 0.2s ease;
  
  &:hover {
    background: rgba(255, 255, 255, 0.7);
    transform: translateY(-2px);
  }
}

.task-result-value {
  font-family: 'JetBrains Mono', monospace;
  font-size: 1.1rem;
  font-weight: 100;
  color: #1f2937;
}

.task-result-label {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.55rem;
  color: #4b5563;
  margin-top: 4px;
  text-transform: uppercase;
  letter-spacing: 0.03em;
  font-weight: 100;
}
</style>