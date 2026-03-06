<template>
  <div class="test-run">
    <h1 class="page-title">运行测试</h1>
    
    <div class="test-form">
      <div class="form-group">
        <label>选择模型</label>
        <select v-model="selectedModel">
          <option v-for="m in models" :key="m.id" :value="m.id">{{ m.name }}</option>
        </select>
      </div>
      
      <div class="form-group">
        <label>测试类型</label>
        <select v-model="testType">
          <option value="single">单次测试</option>
          <option value="concurrent">并发测试</option>
          <option value="round">轮询测试</option>
        </select>
      </div>
      
      <div class="form-group" v-if="testType === 'concurrent'">
        <label>并发数</label>
        <input type="number" v-model="concurrency" min="1" max="200" />
      </div>
      
      <div class="form-group" v-if="testType === 'round'">
        <label>轮次</label>
        <input type="number" v-model="rounds" min="1" max="100" />
      </div>
      
      <div class="form-group">
        <label>测试 Prompt</label>
        <textarea v-model="prompt" rows="4" placeholder="输入测试内容..."></textarea>
      </div>
      
      <div class="form-actions">
        <button class="btn-primary" @click="startTest" :disabled="isRunning">
          {{ isRunning ? '测试中...' : '开始测试' }}
        </button>
        <button class="btn-secondary" @click="stopTest" v-if="isRunning">停止</button>
      </div>
    </div>
    
    <!-- 实时结果 -->
    <div class="results-panel" v-if="results.length > 0">
      <h3>测试结果</h3>
      <div class="results-table">
        <table>
          <thead>
            <tr>
              <th>轮次</th>
              <th>TTFT (ms)</th>
              <th>TPS</th>
              <th>Token数</th>
              <th>状态</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(r, i) in results" :key="i">
              <td>{{ i + 1 }}</td>
              <td>{{ (r.ttft * 1000).toFixed(0) }}</td>
              <td>{{ r.tps.toFixed(2) }}</td>
              <td>{{ r.tokens }}</td>
              <td>
                <span :class="['status', r.success ? 'success' : 'error']">
                  {{ r.success ? '成功' : '失败' }}
                </span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      
      <div class="result-summary">
        <div class="summary-item">
          <span>平均TTFT:</span>
          <strong>{{ (summary.avgTtft * 1000).toFixed(0) }}ms</strong>
        </div>
        <div class="summary-item">
          <span>平均TPS:</span>
          <strong>{{ summary.avgTps.toFixed(2) }}</strong>
        </div>
        <div class="summary-item">
          <span>成功率:</span>
          <strong>{{ (summary.successRate * 100).toFixed(1) }}%</strong>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, reactive } from 'vue'

const models = ref([{ id: 'MiniMax-Text-01', name: 'MiniMax Text 01' }])
const selectedModel = ref('MiniMax-Text-01')
const testType = ref('single')
const concurrency = ref(10)
const rounds = ref(5)
const prompt = ref('请介绍一下人工智能的发展历史')
const isRunning = ref(false)
const results = ref<any[]>([])

const summary = computed(() => {
  if (results.value.length === 0) return { avgTtft: 0, avgTps: 0, successRate: 0 }
  const success = results.value.filter(r => r.success)
  return {
    avgTtft: results.value.reduce((a, b) => a + b.ttft, 0) / results.value.length,
    avgTps: results.value.filter(r => r.success).reduce((a, b) => a + b.tps, 0) / success.length || 0,
    successRate: success.length / results.value.length
  }
})

async function startTest() {
  isRunning.value = true
  results.value = []
  
  try {
    const res = await fetch('/api/test/start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        model: selectedModel.value,
        type: testType.value,
        concurrency: concurrency.value,
        rounds: rounds.value,
        prompt: prompt.value
      })
    })
    const data = await res.json()
    results.value = data.results
  } catch (e) {
    console.error('Test failed:', e)
  } finally {
    isRunning.value = false
  }
}

function stopTest() {
  isRunning.value = false
}
</script>

<style lang="scss" scoped>
.test-run {
  .page-title {
    margin-bottom: 24px;
    font-size: 24px;
    font-weight: 600;
  }
}

.test-form {
  background: var(--white);
  padding: 24px;
  border-radius: 8px;
  margin-bottom: 24px;
}

.form-group {
  margin-bottom: 16px;
  
  label {
    display: block;
    margin-bottom: 8px;
    font-weight: 500;
  }
  
  input, select, textarea {
    width: 100%;
    padding: 10px 12px;
    border: 1px solid var(--gray-300);
    border-radius: 6px;
    font-size: 14px;
    
    &:focus {
      outline: none;
      border-color: var(--primary);
    }
  }
  
  textarea {
    resize: vertical;
  }
}

.form-actions {
  display: flex;
  gap: 12px;
  margin-top: 24px;
}

.btn-primary, .btn-secondary {
  padding: 10px 24px;
  border: none;
  border-radius: 6px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  
  &:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }
}

.btn-primary {
  background: var(--primary);
  color: white;
  
  &:hover:not(:disabled) {
    background: #ff5722;
  }
}

.btn-secondary {
  background: var(--gray-200);
  
  &:hover {
    background: var(--gray-300);
  }
}

.results-panel {
  background: var(--white);
  padding: 24px;
  border-radius: 8px;
  
  h3 {
    margin-bottom: 16px;
  }
}

.results-table {
  overflow-x: auto;
  
  table {
    width: 100%;
    border-collapse: collapse;
    
    th, td {
      padding: 12px;
      text-align: left;
      border-bottom: 1px solid var(--gray-200);
    }
    
    th {
      font-weight: 600;
      background: var(--gray-100);
    }
  }
}

.status {
  display: inline-block;
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 12px;
  
  &.success {
    background: rgba(34, 197, 94, 0.15);
    color: var(--success);
  }
  
  &.error {
    background: rgba(239, 68, 68, 0.15);
    color: var(--error);
  }
}

.result-summary {
  display: flex;
  gap: 32px;
  margin-top: 24px;
  padding-top: 24px;
  border-top: 1px solid var(--gray-200);
  
  .summary-item {
    span {
      color: var(--gray-500);
      margin-right: 8px;
    }
    
    strong {
      color: var(--primary);
    }
  }
}
</style>