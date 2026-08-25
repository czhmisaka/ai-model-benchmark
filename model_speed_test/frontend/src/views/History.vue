<template>
  <div class="history">
    <h1 class="page-title">测试历史</h1>
    
    <!-- 图表区域 -->
    <div class="charts-section" v-if="selectedGroup">
      <div class="chart-card">
        <h3 class="chart-title">性能趋势</h3>
        <div ref="trendChartRef" class="chart-container"></div>
      </div>
      <div class="chart-card">
        <h3 class="chart-title">模型对比</h3>
        <div ref="compareChartRef" class="chart-container"></div>
      </div>
      <div class="chart-card">
        <h3 class="chart-title">延迟分布</h3>
        <div ref="distChartRef" class="chart-container"></div>
      </div>
      <button class="btn-close-charts" @click="selectedGroup = null">关闭图表</button>
    </div>
    
    <div class="filters" v-else>
      <input v-model="search" placeholder="搜索模型或测试内容..." class="search-input" />
      <select v-model="filterModel">
        <option value="">全部模型</option>
        <option v-for="m in models" :key="m" :value="m">{{ m }}</option>
      </select>
      <input type="date" v-model="filterDate" />
    </div>
    
    <div class="history-list" v-if="!selectedGroup">
      <div v-for="item in filteredHistory" :key="item.group_id" class="history-item">
        <div class="item-header">
          <span class="model-name">{{ item.name || item.group_id }}</span>
          <span class="test-time">{{ formatTime(item.start_time) }}</span>
        </div>
        <div class="item-meta">
          <span class="meta-tag" v-if="item.config?.models">{{ item.config.models.length }} 模型</span>
          <span class="meta-tag" v-if="item.config?.test_cases">{{ item.config.test_cases.length }} 用例</span>
          <span class="meta-tag">{{ item.total_rounds }} 轮</span>
        </div>
        <div class="item-cases" v-if="item.config?.test_cases?.length">
          <div v-for="tc in item.config.test_cases" :key="tc" class="case-row">
            <span class="case-name">{{ tc }}</span>
            <span v-if="item.config?.case_folder_map?.[tc]?.folder_name" class="folder-tag">📁 {{ item.config.case_folder_map[tc].folder_name }}</span>
          </div>
        </div>
        <div class="item-metrics">
          <span class="metric success">✓ {{ item.success_count || 0 }}</span>
          <span class="metric failed" v-if="item.failed_count">✗ {{ item.failed_count }}</span>
        </div>
        <div class="item-actions">
          <button @click="viewCharts(item)" class="btn-chart">📊 图表</button>
          <button @click="viewDetail(item)">详情</button>
          <button @click="deleteItem(item)" class="btn-delete">删除</button>
        </div>
      </div>
    </div>
    
    <!-- 详情面板 -->
    <div class="detail-panel" v-if="selectedGroup && !showCharts">
      <h3>测试组详情</h3>
      <div class="detail-stats">
        <div class="stat-item">
          <div class="stat-value">{{ selectedGroup.success_count || 0 }}</div>
          <div class="stat-label">成功</div>
        </div>
        <div class="stat-item">
          <div class="stat-value">{{ selectedGroup.failed_count || 0 }}</div>
          <div class="stat-label">失败</div>
        </div>
        <div class="stat-item">
          <div class="stat-value">{{ selectedGroup.total_rounds || 0 }}</div>
          <div class="stat-label">总轮数</div>
        </div>
        <div class="stat-item" v-if="selectedGroup.total_duration_seconds">
          <div class="stat-value">{{ formatDuration(selectedGroup.total_duration_seconds) }}</div>
          <div class="stat-label">总耗时</div>
        </div>
      </div>
        <div class="export-actions">
          <button @click="showReportPreview" class="btn-export">📊 预览报告</button>
          <button @click="exportPDF" class="btn-export btn-pdf">📄 PDF</button>
          <button @click="exportMarkdown" class="btn-export btn-md">📝 Markdown</button>
          <button @click="exportExcel" class="btn-export btn-excel">📊 Excel</button>
          <button @click="exportAll" class="btn-export btn-all">📦 一键导出全部</button>
        </div>
      <button @click="showCharts = true" class="btn-primary">查看图表分析</button>
      <button @click="selectedGroup = null; showCharts = false" class="btn-secondary">返回列表</button>
    </div>
    
    <div class="pagination" v-if="!selectedGroup">
      <button @click="prevPage" :disabled="page <= 1">上一页</button>
      <span>{{ page }} / {{ totalPages }}</span>
      <button @click="nextPage" :disabled="page >= totalPages">下一页</button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import * as echarts from 'echarts'
import ReportPreviewModal from '../components/ReportPreviewModal.vue'

const history = ref<any[]>([])
const search = ref('')
const filterModel = ref('')
const filterDate = ref('')
const page = ref(1)
const pageSize = 20
const models = ref<string[]>([])

// 详情和图表
const selectedGroup = ref<any>(null)
const showCharts = ref(false)
const showPreview = ref(false)
const trendChartRef = ref<HTMLElement | null>(null)
const compareChartRef = ref<HTMLElement | null>(null)
const distChartRef = ref<HTMLElement | null>(null)
let trendChart: echarts.ECharts | null = null
let compareChart: echarts.ECharts | null = null
let distChart: echarts.ECharts | null = null

// 加载历史数据
async function loadHistory() {
  try {
    const res = await fetch('/api/history?limit=100')
    const data = await res.json()
    if (data.success) {
      history.value = data.data || []
    }
  } catch (e) {
    console.error('加载历史失败:', e)
  }
}

// 加载模型列表
async function loadModels() {
  try {
    const res = await fetch('/api/models')
    const data = await res.json()
    if (data.success) {
      models.value = data.data || []
    }
  } catch (e) {
    console.error('加载模型列表失败:', e)
  }
}

const filteredHistory = computed(() => {
  return history.value.filter(h => {
    const config = h.config || {}
    const modelNames = config.models || []
    if (filterModel.value && !modelNames.includes(filterModel.value)) return false
    if (search.value && !(h.name || h.group_id || '').includes(search.value)) return false
    return true
  }).slice((page.value - 1) * pageSize, page.value * pageSize)
})

const totalPages = computed(() => Math.ceil(history.value.length / pageSize))

function prevPage() { if (page.value > 1) page.value-- }
function nextPage() { if (page.value < totalPages.value) page.value++ }

// 格式化总耗时
function formatDuration(seconds: number): string {
  if (!seconds) return '--'
  const minutes = Math.floor(seconds / 60)
  const secs = (seconds % 60).toFixed(1)
  if (minutes > 0) {
    return `${minutes}分${secs}秒`
  }
  return `${secs}秒`
}

function formatTime(timestamp: string) {
  if (!timestamp) return '--'
  return new Date(timestamp).toLocaleString('zh-CN')
}

function viewDetail(item: any) {
  selectedGroup.value = item
  showCharts.value = false
}

async function viewCharts(item: any) {
  selectedGroup.value = item
  showCharts.value = true
  await nextTick()
  setTimeout(() => {
    renderCharts(item)
  }, 100)
}

async function renderCharts(group: any) {
  // 获取测试结果
  try {
    const res = await fetch(`/api/history/${group.group_id}/results`)
    const data = await res.json()
    if (!data.success || !data.data) return
    
    const results = data.data
    
    // 按模型分组
    const modelStats: Record<string, { ttft: number[], tpft: number[], tps: number[], tokens: number[] }> = {}
    results.forEach((r: any) => {
      const model = r.model_name
      if (!modelStats[model]) {
        modelStats[model] = { ttft: [], tpft: [], tps: [], tokens: [] }
      }
      if (r.ttft_seconds) modelStats[model].ttft.push(r.ttft_seconds * 1000) // 转换为毫秒
      if (r.tpft_seconds) modelStats[model].tpft.push(r.tpft_seconds * 1000)
      if (r.tokens_per_second) modelStats[model].tps.push(r.tokens_per_second)
      if (r.output_tokens) modelStats[model].tokens.push(r.output_tokens)
    })
    
    // 1. 性能趋势图（折线图）
    if (trendChartRef.value) {
      if (trendChart) trendChart.dispose()
      trendChart = echarts.init(trendChartRef.value)
      
      const series: any[] = []
      const colors = ['#FF4500', '#48DBFB', '#1DD1A1', '#FECA57', '#FF6B6B']
      let colorIdx = 0
      
      Object.entries(modelStats).forEach(([model, stats]) => {
        series.push({
          name: model,
          type: 'line',
          data: stats.tps,
          smooth: true,
          lineStyle: { color: colors[colorIdx % colors.length] },
          itemStyle: { color: colors[colorIdx % colors.length] }
        })
        colorIdx++
      })
      
      trendChart.setOption({
        tooltip: { trigger: 'axis' },
        legend: { data: Object.keys(modelStats), textStyle: { color: '#aaa' } },
        grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
        xAxis: { 
          type: 'category', 
          data: results.map((_: any, i: number) => `R${i + 1}`),
          axisLine: { lineStyle: { color: '#444' } }
        },
        yAxis: { 
          type: 'value', 
          name: 'Tokens/s',
          axisLine: { lineStyle: { color: '#444' } },
          splitLine: { lineStyle: { color: '#333' } }
        },
        series
      })
    }
    
    // 2. 模型对比雷达图
    if (compareChartRef.value) {
      if (compareChart) compareChart.dispose()
      compareChart = echarts.init(compareChartRef.value)
      
      const radarData = Object.entries(modelStats).map(([model, stats]) => {
        const avgTps = stats.tps.length ? stats.tps.reduce((a, b) => a + b, 0) / stats.tps.length : 0
        const avgTtft = stats.ttft.length ? stats.ttft.reduce((a, b) => a + b, 0) / stats.ttft.length : 0
        const avgTokens = stats.tokens.length ? stats.tokens.reduce((a, b) => a + b, 0) / stats.tokens.length : 0
        
        // 归一化到 0-100
        return {
          value: [
            Math.min(avgTps * 10, 100), // TPS (假设100 t/s为满分)
            Math.max(0, 100 - avgTtft), // TTFT (越低越好)
            Math.min(avgTokens / 5, 100), // Tokens
          ],
          name: model
        }
      })
      
      compareChart.setOption({
        tooltip: {},
        legend: { data: Object.keys(modelStats), bottom: 0, textStyle: { color: '#aaa' } },
        radar: {
          indicator: [
            { name: '速度 (TPS)', max: 100 },
            { name: '响应 (TTFT)', max: 100 },
            { name: '输出量', max: 100 }
          ],
          axisName: { color: '#aaa' },
          splitArea: { areaStyle: { color: ['#222', '#2a2a2a'] } }
        },
        series: [{
          type: 'radar',
          data: radarData,
          itemStyle: { color: '#FF4500' },
          areaStyle: { opacity: 0.3 }
        }]
      })
    }
    
    // 3. 延迟分布直方图
    if (distChartRef.value) {
      if (distChart) distChart.dispose()
      distChart = echarts.init(distChartRef.value)
      
      // 收集所有 TTFT 数据
      const allTtft: number[] = []
      Object.values(modelStats).forEach(stats => {
        allTtft.push(...stats.ttft)
      })
      
      // 创建直方图数据
      const bins = 10
      const max = Math.max(...allTtft, 100)
      const binSize = max / bins
      const histogram: number[] = new Array(bins).fill(0)
      const xAxis: string[] = []
      
      for (let i = 0; i < bins; i++) {
        const start = i * binSize
        const end = (i + 1) * binSize
        xAxis.push(`${start.toFixed(0)}-${end.toFixed(0)}ms`)
        
        allTtft.forEach(v => {
          if (v >= start && v < end) histogram[i]++
        })
      }
      
      distChart.setOption({
        tooltip: { trigger: 'axis' },
        grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
        xAxis: { 
          type: 'category', 
          data: xAxis,
          axisLine: { lineStyle: { color: '#444' } }
        },
        yAxis: { 
          type: 'value',
          axisLine: { lineStyle: { color: '#444' } },
          splitLine: { lineStyle: { color: '#333' } }
        },
        series: [{
          type: 'bar',
          data: histogram,
          itemStyle: { 
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: '#FF4500' },
              { offset: 1, color: '#ff6b2c' }
            ])
          },
          barWidth: '60%'
        }]
      })
    }
    
  } catch (e) {
    console.error('渲染图表失败:', e)
  }
}

// 导出功能
function showReportPreview() {
  showPreview.value = true
}

function exportPDF() {
  if (selectedGroup.value) {
    window.open(`/api/history/${selectedGroup.value.group_id}/report/pdf`, "_blank")
  }
}

function exportMarkdown() {
  if (selectedGroup.value) {
    window.open(`/api/history/${selectedGroup.value.group_id}/report/markdown`, "_blank")
  }
}

function exportExcel() {
  if (selectedGroup.value) {
    window.open(`/api/history/${selectedGroup.value.group_id}/report/excel`, "_blank")
  }
}

function exportAll() {
  if (selectedGroup.value) {
    window.open(`/api/history/${selectedGroup.value.group_id}/report/all`, "_blank")
  }
}

function deleteItem(item: any) {
  if (!confirm('确定删除此测试记录吗？')) return
  fetch(`/api/history/${item.group_id}`, { method: 'DELETE' })
    .then(res => res.json())
    .then(data => {
      if (data.success) {
        history.value = history.value.filter(h => h.group_id !== item.group_id)
      }
    })
}

onMounted(() => {
  loadHistory()
  loadModels()
})

onUnmounted(() => {
  // 释放图表实例，避免页面切换后 canvas/监听器泄漏
  if (trendChart) { trendChart.dispose(); trendChart = null }
  if (compareChart) { compareChart.dispose(); compareChart = null }
  if (distChart) { distChart.dispose(); distChart = null }
})

// 窗口大小变化时重绘图表
watch(() => selectedGroup.value, (val) => {
  if (val && showCharts.value) {
    setTimeout(() => renderCharts(val), 200)
  }
})
</script>

<style lang="scss" scoped>
.history {
  .page-title {
    margin-bottom: 24px;
    font-size: 24px;
    font-weight: 600;
  }
}

.charts-section {
  position: relative;
  margin-bottom: 24px;
  
  .btn-close-charts {
    position: absolute;
    top: 0;
    right: 0;
    padding: 8px 16px;
    background: var(--gray-700);
    color: var(--white);
    border: none;
    border-radius: 6px;
    cursor: pointer;
    
    &:hover {
      background: var(--gray-600);
    }
  }
  
  .chart-card {
    background: var(--gray-800);
    border-radius: 12px;
    padding: 16px;
    margin-bottom: 16px;
    
    .chart-title {
      font-size: 14px;
      color: var(--gray-300);
      margin-bottom: 12px;
    }
    
    .chart-container {
      width: 100%;
      height: 300px;
    }
  }
}

.filters {
  display: flex;
  gap: 12px;
  margin-bottom: 24px;
  
  .search-input {
    flex: 1;
    padding: 10px 12px;
    border: 1px solid var(--gray-300);
    border-radius: 6px;
  }
  
  input, select {
    padding: 10px 12px;
    border: 1px solid var(--gray-300);
    border-radius: 6px;
  }
}

.history-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.history-item {
  background: var(--gray-800);
  padding: 16px;
  border-radius: 8px;
  border: 1px solid var(--gray-700);
  
  .item-header {
    display: flex;
    justify-content: space-between;
    margin-bottom: 8px;
    
    .model-name {
      font-weight: 600;
      color: var(--primary);
    }
    
    .test-time {
      color: var(--gray-400);
      font-size: 14px;
    }
  }
  
  .item-meta {
    display: flex;
    gap: 8px;
    margin-bottom: 8px;
    
    .meta-tag {
      font-size: 12px;
      padding: 2px 8px;
      background: var(--gray-700);
      color: var(--gray-300);
      border-radius: 4px;
    }
  }

  .item-cases {
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
    margin-bottom: 12px;

    .case-row {
      display: inline-flex;
      align-items: center;
      gap: 4px;

      .case-name {
        font-size: 12px;
        color: var(--gray-300);
        padding: 1px 6px;
        background: var(--gray-750);
        border-radius: 3px;
        border: 1px solid var(--gray-600);
      }

      .folder-tag {
        font-size: 11px;
        color: var(--accent);
        padding: 1px 5px;
        border: 1px solid var(--accent-dim);
        border-radius: 3px;
        white-space: nowrap;
      }
    }
  }
  
  .item-metrics {
    display: flex;
    gap: 16px;
    margin-bottom: 12px;
    
    .metric {
      font-size: 14px;
      font-weight: 600;
      
      &.success { color: var(--accent-green); }
      &.failed { color: var(--accent-red); }
    }
  }
  
  .item-actions {
    display: flex;
    gap: 8px;
    
    button {
      padding: 6px 12px;
      border: 1px solid var(--gray-600);
      background: var(--gray-700);
      color: var(--gray-200);
      border-radius: 4px;
      cursor: pointer;
      
      &:hover {
        background: var(--gray-600);
      }
      
      &.btn-chart {
        background: var(--primary-dim);
        border-color: var(--primary);
        color: var(--primary);
      }
      
      &.btn-delete:hover {
        background: rgba(255, 107, 107, 0.2);
        border-color: var(--accent-red);
        color: var(--accent-red);
      }
    }
  }
}

.detail-panel {

  .export-actions {
    display: flex;
    gap: 12px;
    margin-bottom: 20px;
    flex-wrap: wrap;
  }

  .btn-export {
    padding: 10px 20px;
    border: 1px solid var(--gray-600);
    background: var(--gray-700);
    color: var(--gray-200);
    border-radius: 6px;
    cursor: pointer;
    font-size: 14px;
    display: flex;
    align-items: center;
    gap: 6px;

    &:hover {
      background: var(--gray-600);
    }

    &.btn-pdf {
      background: var(--primary-dim);
      border-color: var(--primary);
      color: var(--primary);

      &:hover {
        background: var(--primary);
        color: white;
      }
    }

    &.btn-md {
      background: var(--accent-green-dim);
      border-color: var(--accent-green);
      color: var(--accent-green);

      &:hover {
        background: var(--accent-green);
        color: white;
      }
    }

    &.btn-excel {
      background: var(--accent-blue-dim);
      border-color: var(--accent-blue);
      color: var(--accent-blue);

      &:hover {
        background: var(--accent-blue);
        color: white;
      }
    }
  }

  background: var(--gray-800);
  padding: 24px;
  border-radius: 12px;
  
  h3 {
    margin-bottom: 16px;
  }
  
  .detail-stats {
    display: flex;
    gap: 24px;
    margin-bottom: 24px;
    
    .stat-item {
      text-align: center;
      
      .stat-value {
        font-size: 32px;
        font-weight: 700;
        color: var(--white);
      }
      
      .stat-label {
        font-size: 14px;
        color: var(--gray-400);
      }
    }
  }
  
  button {
    margin-right: 12px;
    padding: 10px 20px;
    border-radius: 6px;
    cursor: pointer;
    
    &.btn-primary {
      background: var(--primary);
      color: var(--white);
      border: none;
      
      &:hover {
        background: #ff5722;
      }
    }
    
    &.btn-secondary {
      background: transparent;
      border: 1px solid var(--gray-600);
      color: var(--gray-300);
      
      &:hover {
        background: var(--gray-700);
      }
    }
  }
}

.pagination {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 16px;
  margin-top: 24px;
  
  button {
    padding: 8px 16px;
    border: 1px solid var(--gray-600);
    background: var(--gray-700);
    color: var(--gray-200);
    border-radius: 6px;
    cursor: pointer;
    
    &:disabled {
      opacity: 0.5;
      cursor: not-allowed;
    }
    
    &:hover:not(:disabled) {
      background: var(--gray-600);
    }
  }
}
</style>