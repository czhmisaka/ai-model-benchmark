<template>
  <div class="modal-overlay" :class="{ show: visible }" @click.self="$emit('close')">
    <div class="modal task-detail-modal" :class="{ animating: isAnimating }">
      <div class="modal-title">
        任务详情
        <span class="task-detail-subtitle">{{ taskData.model_name }} → {{ taskData.case_name }}</span>
      </div>
      
      <div class="task-detail-content" v-if="taskData.sub_tasks">
        <!-- 汇总统计 -->
        <div class="task-detail-summary">
          <div class="detail-stat-grid">
            <div class="detail-stat-item">
              <div class="detail-stat-value">{{ taskData.avgTtft || '--' }}s</div>
              <div class="detail-stat-label">首Token (TTFT)</div>
            </div>
            <div class="detail-stat-item">
              <div class="detail-stat-value">{{ taskData.avgTpft || '--' }}s</div>
              <div class="detail-stat-label">生成时间 (TPFT)</div>
            </div>
            <div class="detail-stat-item">
              <div class="detail-stat-value">{{ taskData.avgTokens || '--' }}</div>
              <div class="detail-stat-label">输出Token</div>
            </div>
            <div class="detail-stat-item">
              <div class="detail-stat-value">{{ taskData.avgSpeed || '--' }}</div>
              <div class="detail-stat-label">总速度/s</div>
            </div>
            <div class="detail-stat-item accent" v-if="taskData.avgAnswerSpeed && taskData.avgAnswerSpeed !== '--'">
              <div class="detail-stat-value">{{ taskData.avgAnswerSpeed }}</div>
              <div class="detail-stat-label">Answer速度/s</div>
            </div>
            <div class="detail-stat-item" v-if="taskData.avgThinkTokens && taskData.avgThinkTokens !== '--'">
              <div class="detail-stat-value">{{ taskData.avgThinkTokens }}</div>
              <div class="detail-stat-label">Think Tokens</div>
            </div>
            <div class="detail-stat-item" v-if="taskData.avgAnswerTokens && taskData.avgAnswerTokens !== '--'">
              <div class="detail-stat-value">{{ taskData.avgAnswerTokens }}</div>
              <div class="detail-stat-label">Answer Tokens</div>
            </div>
          </div>
        </div>
        
        <!-- 详细轮次列表 -->
        <div class="task-detail-rounds">
          <div class="detail-rounds-title">各轮次详细数据</div>
          <div class="detail-rounds-list">
            <div 
              v-for="(subTask, subId) in taskData.sub_tasks" 
              :key="subId"
              class="detail-round-item"
              :class="subTask.status"
            >
              <div class="detail-round-header">
                <span class="detail-round-number">{{ subTask.name }}</span>
                <span class="detail-round-status" :class="subTask.status">
                  {{ subTask.status === 'done' ? '✓ 成功' : subTask.status === 'error' ? '✗ 失败' : subTask.status === 'running' ? '⟳ 进行中' : '○ 待测试' }}
                </span>
              </div>
              <div class="detail-round-metrics" v-if="subTask.status === 'done' && subTask.metrics">
                <div class="metric-row">
                  <span class="metric-label">速度:</span>
                  <span class="metric-value">{{ subTask.metrics.speed || '--' }} t/s</span>
                  <span class="metric-label" v-if="subTask.metrics.answerSpeed"> (Answer: {{ subTask.metrics.answerSpeed }} t/s)</span>
                </div>
                <div class="metric-row">
                  <span class="metric-label">TTFT:</span>
                  <span class="metric-value">{{ subTask.metrics.ttft || '--' }}s</span>
                  <span class="metric-label"> TPFT:</span>
                  <span class="metric-value">{{ subTask.metrics.tpft || '--' }}s</span>
                </div>
                <div class="metric-row" v-if="subTask.metrics.tokens">
                  <span class="metric-label">Tokens:</span>
                  <span class="metric-value">{{ subTask.metrics.tokens }}</span>
                  <span class="metric-label" v-if="subTask.metrics.thinkTokens"> (Think: {{ subTask.metrics.thinkTokens }})</span>
                  <span class="metric-label" v-if="subTask.metrics.answerTokens"> (Answer: {{ subTask.metrics.answerTokens }})</span>
                </div>
                <div class="metric-row" v-if="subTask.metrics.answerTime !== undefined && subTask.metrics.answerTime !== null">
                  <span class="metric-label" v-if="subTask.metrics.thinkTime !== undefined && subTask.metrics.thinkTime !== null && subTask.metrics.thinkTime > 0">Think时间:</span>
                  <span class="metric-value" v-if="subTask.metrics.thinkTime !== undefined && subTask.metrics.thinkTime !== null && subTask.metrics.thinkTime > 0">{{ subTask.metrics.thinkTime }}s</span>
                  <span class="metric-label"> Answer时间:</span>
                  <span class="metric-value">{{ subTask.metrics.answerTime }}s</span>
                </div>
              </div>
              <!-- 输入/输出显示 -->
              <div class="detail-round-io" v-if="subTask.status === 'done' || subTask.status === 'running'">
                <div class="io-section" v-if="subTask.prompt">
                  <div class="io-label">输入 Prompt:</div>
                  <div class="io-content input">{{ subTask.prompt }}</div>
                </div>
                <div class="io-section" v-if="subTask.output">
                  <div class="io-label">输出预览:</div>
                  <div class="io-content output">{{ subTask.output }}</div>
                </div>
                <!-- Think 内容显示 -->
                <div class="io-section" v-if="subTask.think_content">
                  <div class="io-label">💭 思考内容 (Think):</div>
                  <div class="io-content think">{{ subTask.think_content }}</div>
                </div>
                <!-- Answer 内容显示 -->
                <div class="io-section" v-if="subTask.answer_content">
                  <div class="io-label">✍️ 回答内容 (Answer):</div>
                  <div class="io-content answer">{{ subTask.answer_content }}</div>
                </div>
              </div>
              <!-- 校对结果展示 -->
              <div class="detail-round-evaluation" v-if="subTask.evaluation">
                <div class="evaluation-badge" :class="{ correct: subTask.evaluation.is_correct, incorrect: !subTask.evaluation.is_correct }">
                  <span class="evaluation-icon">{{ subTask.evaluation.is_correct ? '✓' : '✗' }}</span>
                  <span class="evaluation-label">校对结果:</span>
                  <span class="evaluation-rate">{{ subTask.evaluation.rate }}/10</span>
                </div>
                <div class="evaluation-reason" v-if="subTask.evaluation.reason">
                  {{ subTask.evaluation.reason }}
                </div>
              </div>
              <div class="detail-round-error" v-if="subTask.status === 'error'">
                错误: {{ subTask.error || '未知错误' }}
              </div>
            </div>
          </div>
        </div>
      </div>
      
      <div class="form-actions">
        <button class="btn btn-secondary" @click="$emit('close')">关闭</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
interface Evaluation {
  is_correct: boolean
  rate: number
  reason: string
}

interface SubTask {
  name: string
  output: string
  status: string
  metrics: any
  prompt?: string
  error?: string
  evaluation?: Evaluation
  think_content?: string  // 思考内容
  answer_content?: string  // 回答内容
}

interface TaskData {
  model_name: string
  case_name: string
  sub_tasks: Record<string, SubTask>
  avgTtft?: string
  avgTpft?: string
  avgTokens?: string
  avgSpeed?: string
  avgAnswerSpeed?: string
  avgThinkTokens?: string
  avgAnswerTokens?: string
}

interface Props {
  visible: boolean
  taskData: TaskData
  isAnimating?: boolean
}

defineProps<Props>()

defineEmits<{
  close: []
}>()

function trimText(text: string): string {
  if (!text) return ''
  // 只对 prompt 进行压缩处理，保留输出完整内容
  return text.replace(/[\r\n]+/g, ' ').replace(/\s+/g, ' ').trim()
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
  width: 700px;
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
  
  &.animating {
    animation: modalBounceIn 0.4s ease;
  }
}

@keyframes modalBounceIn {
  0% { transform: scale(0.95); opacity: 0; }
  50% { transform: scale(1.02); }
  100% { transform: scale(1); opacity: 1; }
}

.modal-title {
  font-family: 'Space Grotesk', sans-serif;
  font-size: 1rem;
  font-weight: 600;
  color: var(--gray-900);
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--gray-200);
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.task-detail-subtitle {
  font-size: 0.8rem;
  font-weight: 400;
  color: var(--gray-500);
}

.task-detail-content {
  max-height: calc(85vh - 100px);
  overflow-y: auto;
}

.task-detail-summary {
  margin-bottom: 20px;
  padding: 16px;
  background: var(--gray-100);
  border-radius: 8px;
}

.detail-stat-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
}

.detail-stat-item {
  text-align: center;
  
  &.accent .detail-stat-value {
    color: var(--primary);
    font-size: 1.1rem;
  }
}

.detail-stat-value {
  font-family: 'JetBrains Mono', monospace;
  font-size: 1rem;
  font-weight: 600;
  color: var(--gray-900);
}

.detail-stat-label {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.6rem;
  color: var(--gray-500);
  margin-top: 4px;
}

.task-detail-rounds {
  user-select: all !important ;
  margin-top: 16px;
}

.detail-rounds-title {
  user-select: all !important ;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.75rem;
  color: var(--gray-500);
  margin-bottom: 12px;
  text-transform: uppercase;
}

.detail-rounds-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.detail-round-item {
  padding: 12px;
  background: var(--gray-100);
  border-radius: 8px;
  border-left: 3px solid var(--gray-400);
  
  &.done {
    border-left-color: var(--primary);
  }
  
  &.error {
    border-left-color: var(--accent-red);
  }
  
  &.running {
    border-left-color: var(--accent-orange);
  }
}

.detail-round-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.detail-round-number {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.75rem;
  color: var(--gray-900);
}

.detail-round-status {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.65rem;
  padding: 2px 8px;
  border-radius: 4px;
  
  &.done {
    background: var(--primary-dim);
    color: var(--primary);
  }
  
  &.error {
    background: rgba(255,107,107,0.15);
    color: var(--accent-red);
  }
  
  &.running {
    background: rgba(249, 115, 22, 0.15);
    color: var(--accent-orange);
  }
  
  &.pending {
    background: var(--gray-200);
    color: var(--gray-500);
  }
}

.detail-round-metrics {
  font-size: 0.7rem;
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid var(--gray-200);
}

.metric-row {
  display: flex;
  gap: 8px;
  margin-bottom: 4px;
  flex-wrap: wrap;
}

.metric-label {
  color: var(--gray-500);
}

.metric-value {
  color: var(--primary);
  font-family: 'JetBrains Mono', monospace;
}

.detail-round-io {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid var(--gray-200);
}

.io-section {
  margin-bottom: 8px;
  
  &:last-child {
    margin-bottom: 0;
  }
}

.io-label {
  font-size: 0.65rem;
  color: var(--gray-500);
  margin-bottom: 4px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.io-content {
  font-size: 0.7rem;
  padding: 8px;
  border-radius: 4px;
  max-height: 400px;
  overflow-y: auto;
  white-space: pre-wrap;
  word-break: break-word;
  line-height: 1.5;
  
  &.input {
    background: rgba(59, 130, 246, 0.08);
    border: 1px solid rgba(59, 130, 246, 0.2);
    color: var(--gray-700);
  }
  
  &.output {
    background: rgba(34, 197, 94, 0.08);
    border: 1px solid rgba(34, 197, 94, 0.2);
    color: var(--gray-700);
  }
  
  &.think {
    background: rgba(139, 92, 246, 0.08);
    border: 1px solid rgba(139, 92, 246, 0.2);
    color: var(--gray-700);
  }
  
  &.answer {
    background: rgba(34, 197, 94, 0.08);
    border: 1px solid rgba(34, 197, 94, 0.2);
    color: var(--gray-700);
  }
}

.detail-round-error {
  margin-top: 8px;
  padding: 8px;
  background: rgba(255,107,107,0.1);
  border-radius: 4px;
  font-size: 0.7rem;
  color: var(--accent-red);
}

// 校对结果样式
.detail-round-evaluation {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid var(--gray-200);
}

.evaluation-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border-radius: 4px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.7rem;
  
  &.correct {
    background: rgba(34, 197, 94, 0.12);
    border: 1px solid rgba(34, 197, 94, 0.3);
    color: #16a34a;
    
    .evaluation-icon {
      color: #16a34a;
    }
  }
  
  &.incorrect {
    background: rgba(239, 68, 68, 0.12);
    border: 1px solid rgba(239, 68, 68, 0.3);
    color: #dc2626;
    
    .evaluation-icon {
      color: #dc2626;
    }
  }
}

.evaluation-icon {
  font-size: 0.8rem;
  font-weight: 700;
}

.evaluation-label {
  color: var(--gray-600);
}

.evaluation-rate {
  font-weight: 600;
  color: inherit;
}

.evaluation-reason {
  margin-top: 6px;
  font-size: 0.7rem;
  color: var(--gray-600);
  line-height: 1.4;
  padding: 6px 8px;
  background: var(--gray-50);
  border-radius: 4px;
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
}

.btn-secondary {
  &:hover:not(:disabled) {
    background: var(--gray-50);
  }
}
</style>