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
    
    <!-- 实时图表区域 -->
    <div class="charts-panel" v-if="results.length > 0">
      <div class="charts-grid">
        <!-- TTFT 趋势图 -->
        <div class="chart-card">
          <div class="chart-header">
            <span class="chart-title">TTFT 趋势 (ms)</span>
            <span class="chart-badge">{{ latestTTFT }}ms</span>
          </div>
          <v-chart :option="ttftChartOption" autoresize class="chart-container" />
        </div>
        
        <!-- TPS 趋势图 -->
        <div class="chart-card">
          <div class="chart-header">
            <span class="chart-title">TPS 趋势</span>
            <span class="chart-badge">{{ latestTPS }}</span>
          </div>
          <v-chart :option="tpsChartOption" autoresize class="chart-container" />
        </div>
        
        <!-- Token 分布 -->
        <div class="chart-card">
          <div class="chart-header">
            <span class="chart-title">Token 分布</span>
            <span class="chart-badge">{{ totalTokens }} tokens</span>
          </div>
          <v-chart :option="tokenChartOption" autoresize class="chart-container" />
        </div>
        
        <!-- 成功率饼图 -->
        <div class="chart-card">
          <div class="chart-header">
            <span class="chart-title">成功率</span>
            <span class="chart-badge" :class="successRateClass">{{ summary.successRate }}%</span>
          </div>
          <v-chart :option="successChartOption" autoresize class="chart-container" />
        </div>
      </div>
    </div>
    
    <!-- 实时结果表格 -->
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
            <tr v-for="(r, i) in results" :key="i" :class="{ 'row-new': i === results.length - 1 }">
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
        <div class="summary-item">
          <span>总Token:</span>
          <strong>{{ summary.totalTokens }}</strong>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart, BarChart, PieChart } from 'echarts/charts'
import {
  GridComponent,
  TooltipComponent,
  LegendComponent,
  TitleComponent
} from 'echarts/components'

use([
  CanvasRenderer,
  LineChart,
  BarChart,
  PieChart,
  GridComponent,
  TooltipComponent,
  LegendComponent,
  TitleComponent
])

// --- 表单数据 ---
const models = ref([{ id: 'MiniMax-Text-01', name: 'MiniMax Text 01' }])
const selectedModel = ref('MiniMax-Text-01')
const testType = ref('single')
const concurrency = ref(10)
const rounds = ref(5)
const prompt = ref('请介绍一下人工智能的发展历史')
const isRunning = ref(false)
const results = ref<any[]>([])

// --- 计算统计 ---
const summary = computed(() => {
  if (results.value.length === 0) {
    return { avgTtft: 0, avgTps: 0, successRate: 0, totalTokens: 0 }
  }
  const success = results.value.filter(r => r.success)
  return {
    avgTtft: results.value.reduce((a, b) => a + b.ttft, 0) / results.value.length,
    avgTps: success.length > 0
      ? success.reduce((a, b) => a + b.tps, 0) / success.length
      : 0,
    successRate: results.value.length > 0
      ? Math.round((success.length / results.value.length) * 1000) / 10
      : 0,
    totalTokens: results.value.reduce((a, b) => a + (b.tokens || 0), 0)
  }
})

const latestTTFT = computed(() => {
  if (results.value.length === 0) return '--'
  const last = results.value[results.value.length - 1]
  return (last.ttft * 1000).toFixed(0)
})

const latestTPS = computed(() => {
  if (results.value.length === 0) return '--'
  const last = results.value[results.value.length - 1]
  return last.tps.toFixed(2)
})

const totalTokens = computed(() => {
  return results.value.reduce((a, b) => a + (b.tokens || 0), 0)
})

const successRateClass = computed(() => {
  const rate = summary.value.successRate
  if (rate >= 90) return 'badge-success'
  if (rate >= 50) return 'badge-warning'
  return 'badge-danger'
})

// --- 图表配置 ---
const chartColors = {
  primary: '#FF4500',
  secondary: '#666666',
  tertiary: '#CCCCCC',
  light: '#E0E0E0',
  success: '#22C55E',
  danger: '#EF4444',
  warning: '#F59E0B'
}

const chartTextStyle = {
  fontFamily: 'JetBrains Mono, monospace',
  fontSize: 11,
  color: '#666666'
}

const gridStyle = {
  top: 40,
  right: 20,
  bottom: 30,
  left: 50
}

// TTFT 趋势图
const ttftChartOption = computed(() => {
  const successData = results.value
    .map((r, i) => r.success ? [(i + 1), Math.round(r.ttft * 1000)] : null)
    .filter(Boolean)
  const failData = results.value
    .map((r, i) => !r.success ? [(i + 1), Math.round(r.ttft * 1000)] : null)
    .filter(Boolean)

  return {
    grid: gridStyle,
    tooltip: {
      trigger: 'axis',
      textStyle: chartTextStyle,
      backgroundColor: '#FFFFFF',
      borderColor: '#E0E0E0',
      borderWidth: 1,
      formatter: (params: any) => {
        const p = Array.isArray(params) ? params[0] : params
        return `轮次 ${p.data[0]}<br/>TTFT: <b>${p.data[1]}ms</b>`
      }
    },
    xAxis: {
      type: 'value',
      name: '轮次',
      nameTextStyle: { ...chartTextStyle, fontSize: 10 },
      axisLine: { lineStyle: { color: '#E0E0E0', width: 1 } },
      axisTick: { show: false },
      axisLabel: chartTextStyle,
      splitLine: { show: false },
      minInterval: 1
    },
    yAxis: {
      type: 'value',
      name: 'ms',
      nameTextStyle: { ...chartTextStyle, fontSize: 10 },
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: chartTextStyle,
      splitLine: { lineStyle: { color: '#F0F0F0', type: 'dashed', width: 1 } }
    },
    series: [
      {
        name: '成功',
        type: 'line',
        data: successData,
        smooth: true,
        symbol: 'circle',
        symbolSize: 5,
        lineStyle: { color: chartColors.success, width: 1.5 },
        itemStyle: { color: chartColors.success },
        emphasis: { focus: 'series' }
      },
      {
        name: '失败',
        type: 'line',
        data: failData,
        smooth: true,
        symbol: 'diamond',
        symbolSize: 7,
        lineStyle: { color: chartColors.danger, width: 1.5, type: 'dashed' },
        itemStyle: { color: chartColors.danger },
        emphasis: { focus: 'series' }
      }
    ]
  }
})

// TPS 趋势图
const tpsChartOption = computed(() => {
  const successData = results.value
    .filter(r => r.success)
    .map((r) => {
      const realIndex = results.value.indexOf(r) + 1
      return [realIndex, parseFloat(r.tps.toFixed(2))]
    })

  return {
    grid: gridStyle,
    tooltip: {
      trigger: 'axis',
      textStyle: chartTextStyle,
      backgroundColor: '#FFFFFF',
      borderColor: '#E0E0E0',
      borderWidth: 1,
      formatter: (params: any) => {
        const p = Array.isArray(params) ? params[0] : params
        return `轮次 ${p.data[0]}<br/>TPS: <b>${p.data[1]}</b>`
      }
    },
    xAxis: {
      type: 'value',
      name: '轮次',
      nameTextStyle: { ...chartTextStyle, fontSize: 10 },
      axisLine: { lineStyle: { color: '#E0E0E0', width: 1 } },
      axisTick: { show: false },
      axisLabel: chartTextStyle,
      splitLine: { show: false },
      minInterval: 1
    },
    yAxis: {
      type: 'value',
      name: 'tokens/s',
      nameTextStyle: { ...chartTextStyle, fontSize: 10 },
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: chartTextStyle,
      splitLine: { lineStyle: { color: '#F0F0F0', type: 'dashed', width: 1 } }
    },
    series: [{
      name: 'TPS',
      type: 'line',
      data: successData,
      smooth: true,
      symbol: 'circle',
      symbolSize: 5,
      lineStyle: { color: chartColors.primary, width: 2 },
      itemStyle: { color: chartColors.primary },
      areaStyle: {
        color: {
          type: 'linear',
          x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [
            { offset: 0, color: 'rgba(255, 69, 0, 0.15)' },
            { offset: 1, color: 'rgba(255, 69, 0, 0.02)' }
          ]
        }
      },
      markLine: {
        silent: true,
        data: successData.length > 0 ? [{
          type: 'average',
          name: '平均值',
          lineStyle: { color: '#999999', type: 'dashed', width: 1 },
          label: { formatter: '{c}', ...chartTextStyle }
        }] : [],
        symbol: 'none'
      }
    }]
  }
})

// Token 分布图
const tokenChartOption = computed(() => {
  const successResults = results.value.filter(r => r.success)
  const labels = successResults.map((_, i) => `#${i + 1}`)
  const data = successResults.map(r => r.tokens || 0)

  return {
    grid: { ...gridStyle, bottom: 50 },
    tooltip: {
      trigger: 'axis',
      textStyle: chartTextStyle,
      backgroundColor: '#FFFFFF',
      borderColor: '#E0E0E0',
      borderWidth: 1
    },
    xAxis: {
      type: 'category',
      data: labels,
      axisLine: { lineStyle: { color: '#E0E0E0', width: 1 } },
      axisTick: { show: false },
      axisLabel: { ...chartTextStyle, fontSize: 9, rotate: labels.length > 15 ? 45 : 0 }
    },
    yAxis: {
      type: 'value',
      name: 'tokens',
      nameTextStyle: { ...chartTextStyle, fontSize: 10 },
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: chartTextStyle,
      splitLine: { lineStyle: { color: '#F0F0F0', type: 'dashed', width: 1 } }
    },
    series: [{
      type: 'bar',
      data: data,
      barWidth: '60%',
      itemStyle: {
        color: chartColors.primary,
        borderRadius: [3, 3, 0, 0],
        borderColor: chartColors.primary,
        borderWidth: 1,
        opacity: 0.85
      },
      emphasis: {
        itemStyle: { opacity: 1 }
      }
    }]
  }
})

// 成功率饼图
const successChartOption = computed(() => {
  const successCount = results.value.filter(r => r.success).length
  const failCount = results.value.length - successCount

  return {
    tooltip: {
      trigger: 'item',
      textStyle: chartTextStyle,
      backgroundColor: '#FFFFFF',
      borderColor: '#E0E0E0',
      borderWidth: 1,
      formatter: '{b}: {c} ({d}%)'
    },
    legend: {
      bottom: 0,
      textStyle: chartTextStyle,
      itemWidth: 10,
      itemHeight: 10
    },
    series: [{
      type: 'pie',
      radius: ['55%', '78%'],
      center: ['50%', '45%'],
      avoidLabelOverlap: false,
      itemStyle: {
        borderColor: '#FFFFFF',
        borderWidth: 2
      },
      label: {
        show: true,
        position: 'center',
        formatter: `{percent|${summary.value.successRate}%}`,
        rich: {
          percent: {
            fontSize: 22,
            fontFamily: 'JetBrains Mono, monospace',
            fontWeight: 'bold',
            color: chartColors.primary,
            lineHeight: 28
          }
        }
      },
      emphasis: {
        label: { show: true },
        scaleSize: 6
      },
      data: [
        {
          value: successCount,
          name: '成功',
          itemStyle: { color: chartColors.success }
        },
        {
          value: failCount,
          name: '失败',
          itemStyle: { color: chartColors.danger }
        }
      ]
    }]
  }
})

// --- 测试控制 ---
let abortController: AbortController | null = null

async function startTest() {
  isRunning.value = true
  results.value = []

  abortController = new AbortController()
  
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
      }),
      signal: abortController.signal
    })
    const data = await res.json()
    if (data.results) {
      results.value = data.results
    }
  } catch (e: any) {
    if (e.name !== 'AbortError') {
      console.error('Test failed:', e)
    }
  } finally {
    isRunning.value = false
    abortController = null
  }
}

function stopTest() {
  if (abortController) {
    abortController.abort()
    abortController = null
  }
  isRunning.value = false
}
</script>

<style lang="scss" scoped>
.test-run {
  .page-title {
    margin-bottom: var(--space-lg, 24px);
    font-size: 24px;
    font-weight: 600;
    color: var(--line-primary, #000000);
  }
}

.test-form {
  background: var(--bg-white, #FFFFFF);
  padding: var(--space-lg, 24px);
  border: 1px solid var(--line-tertiary, #CCCCCC);
  border-radius: 6px;
  margin-bottom: var(--space-lg, 24px);
}

.form-group {
  margin-bottom: var(--space-md, 16px);
  
  label {
    display: block;
    margin-bottom: var(--space-sm, 8px);
    font-weight: 500;
    font-family: 'JetBrains Mono', monospace;
    font-size: 12px;
    color: var(--line-secondary, #666666);
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }
  
  input, select, textarea {
    width: 100%;
    padding: 10px 12px;
    background: transparent;
    border: 1px solid var(--line-tertiary, #CCCCCC);
    border-radius: 4px;
    font-size: 14px;
    font-family: 'JetBrains Mono', 'Noto Sans SC', monospace;
    transition: border-color var(--duration-fast, 150ms) ease;
    box-sizing: border-box;
    
    &:focus {
      outline: none;
      border-color: var(--line-accent, #FF4500);
      border-width: 2px;
    }
  }
  
  textarea {
    resize: vertical;
    min-height: 80px;
  }
}

.form-actions {
  display: flex;
  gap: 12px;
  margin-top: var(--space-lg, 24px);
}

.btn-primary, .btn-secondary {
  padding: 10px 24px;
  border-radius: 4px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  font-family: 'Space Grotesk', 'Noto Sans SC', sans-serif;
  transition: all var(--duration-fast, 150ms) ease;
  
  &:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
}

.btn-primary {
  background: transparent;
  border: 1px solid var(--line-primary, #000000);
  color: var(--line-primary, #000000);
  
  &:hover:not(:disabled) {
    border-color: var(--line-accent, #FF4500);
    color: var(--line-accent, #FF4500);
    background: rgba(255, 69, 0, 0.05);
  }
}

.btn-secondary {
  background: transparent;
  border: 1px solid var(--line-tertiary, #CCCCCC);
  color: var(--line-secondary, #666666);
  
  &:hover {
    border-color: var(--line-primary, #000000);
    color: var(--line-primary, #000000);
  }
}

// --- 图表面板 ---
.charts-panel {
  margin-bottom: var(--space-lg, 24px);
}

.charts-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-md, 16px);
  
  @media (max-width: 900px) {
    grid-template-columns: 1fr;
  }
}

.chart-card {
  background: var(--bg-white, #FFFFFF);
  border: 1px solid var(--line-tertiary, #CCCCCC);
  border-radius: 6px;
  overflow: hidden;
  transition: border-color var(--duration-fast, 150ms) ease;
  
  &:hover {
    border-color: var(--line-secondary, #666666);
  }
}

.chart-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  border-bottom: 1px solid var(--line-light, #E0E0E0);
}

.chart-title {
  font-size: 13px;
  font-weight: 600;
  font-family: 'Space Grotesk', 'Noto Sans SC', sans-serif;
  color: var(--line-primary, #000000);
}

.chart-badge {
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
  color: var(--line-accent, #FF4500);
  border: 1px solid var(--line-light, #E0E0E0);
  border-radius: 9999px;
  padding: 2px 10px;
  
  &.badge-success { color: var(--success, #22C55E); }
  &.badge-warning { color: var(--warning, #F59E0B); }
  &.badge-danger { color: var(--danger, #EF4444); }
}

.chart-container {
  width: 100%;
  height: 260px;
}

// --- 结果表格 ---
.results-panel {
  background: var(--bg-white, #FFFFFF);
  padding: var(--space-lg, 24px);
  border: 1px solid var(--line-tertiary, #CCCCCC);
  border-radius: 6px;
  
  h3 {
    margin-bottom: var(--space-md, 16px);
    font-family: 'Space Grotesk', 'Noto Sans SC', sans-serif;
    font-size: 16px;
    color: var(--line-primary, #000000);
  }
}

.results-table {
  overflow-x: auto;
  max-height: 400px;
  overflow-y: auto;
  
  table {
    width: 100%;
    border-collapse: collapse;
    
    th, td {
      padding: 10px 12px;
      text-align: left;
      border-bottom: 1px solid var(--line-light, #E0E0E0);
      font-size: 13px;
    }
    
    th {
      font-weight: 600;
      font-family: 'JetBrains Mono', monospace;
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      color: var(--line-secondary, #666666);
      background: rgba(0, 0, 0, 0.02);
      position: sticky;
      top: 0;
      z-index: 1;
    }
    
    td {
      font-family: 'JetBrains Mono', monospace;
      color: var(--line-primary, #000000);
    }
    
    .row-new {
      animation: fadeIn 0.5s ease-out;
    }
  }
}

@keyframes fadeIn {
  from { background: rgba(255, 69, 0, 0.08); }
  to { background: transparent; }
}

.status {
  display: inline-block;
  padding: 3px 10px;
  border-radius: 9999px;
  font-size: 11px;
  font-family: 'JetBrains Mono', monospace;
  
  &.success {
    border: 1px solid var(--success, #22C55E);
    color: var(--success, #22C55E);
  }
  
  &.error {
    border: 1px solid var(--danger, #EF4444);
    color: var(--danger, #EF4444);
  }
}

.result-summary {
  display: flex;
  gap: 32px;
  margin-top: var(--space-lg, 24px);
  padding-top: var(--space-lg, 24px);
  border-top: 1px solid var(--line-light, #E0E0E0);
  
  .summary-item {
    span {
      color: var(--line-secondary, #666666);
      margin-right: 8px;
      font-size: 13px;
    }
    
    strong {
      color: var(--line-accent, #FF4500);
      font-family: 'JetBrains Mono', monospace;
      font-size: 16px;
    }
  }
}
</style>