<template>
  <div class="modal-overlay" v-if="visible" @click.self="close">
    <div class="report-preview-modal">
      <div class="modal-header">
        <h3>📊 报告预览</h3>
        <div class="header-actions">
          <select v-model="selectedTemplate" @change="switchTemplate" class="template-select">
            <option v-for="t in templates" :key="t" :value="t">{{ t === 'default' ? '📋 标准报告' : t === 'minimal' ? '📝 极简报告' : t }}</option>
          </select>
          <button @click="exportPDF" class="btn-action">📄 PDF</button>
          <button @click="exportMarkdown" class="btn-action">📝 Markdown</button>
          <button @click="exportExcel" class="btn-action">📊 Excel</button>
          <button @click="copyLink" class="btn-action">🔗 分享</button>
          <button @click="close" class="btn-close">✕</button>
        </div>
      </div>
      
      <div class="modal-body">
        <!-- 加载状态 -->
        <div v-if="loading" class="loading">
          <div class="spinner"></div>
          <span>加载报告中...</span>
        </div>
        
        <!-- 报告内容 -->
        <div v-else class="report-content markdown-body" v-html="renderedContent"></div>
      </div>
      
      <!-- 统计概览 -->
      <div class="modal-footer" v-if="!loading">
        <div class="stat-item">
          <span class="stat-label">总测试数</span>
          <span class="stat-value">{{ stats.total }}</span>
        </div>
        <div class="stat-item">
          <span class="stat-label">成功率</span>
          <span class="stat-value">{{ stats.successRate }}%</span>
        </div>
        <div class="stat-item">
          <span class="stat-label">平均 TTFT</span>
          <span class="stat-value">{{ stats.avgTtft }}ms</span>
        </div>
        <div class="stat-item">
          <span class="stat-label">平均 TPS</span>
          <span class="stat-value">{{ stats.avgTps }}</span>
        </div>
      </div>
    </div>

    <div class="rpm-toast" :class="[toastType, { show: toastVisible }]">{{ toastMessage }}</div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { marked } from 'marked'

// 轻量 toast
const toastVisible = ref(false)
const toastMessage = ref('')
const toastType = ref<'success' | 'error'>('success')
function showToast(msg: string, type: 'success' | 'error' = 'success') {
  toastMessage.value = msg
  toastType.value = type
  toastVisible.value = true
  setTimeout(() => { toastVisible.value = false }, 2500)
}

const props = defineProps<{
  visible: boolean
  groupId: string
}>()

const emit = defineEmits(['close', 'export'])

const loading = ref(false)
const renderedContent = ref('')
const selectedTemplate = ref('default')
const templates = ref<string[]>(['default', 'minimal'])
const stats = ref({
  total: 0,
  successRate: 0,
  avgTtft: 0,
  avgTps: 0
})

// 加载可用模板列表
async function loadTemplates() {
  try {
    const res = await fetch('/api/report/templates')
    const data = await res.json()
    if (data.success && data.data) {
      templates.value = data.data
    }
  } catch (e) {
    console.error('加载模板列表失败:', e)
  }
}

// 加载报告内容
async function loadReport() {
  if (!props.groupId) return
  
  loading.value = true
  
  try {
    // 获取 Markdown 内容（带模板参数）
    const res = await fetch(`/api/history/${props.groupId}/report/markdown?template=${selectedTemplate.value}`)
    const data = await res.json()
    
    if (data.success) {
      // 使用 marked 解析 Markdown
      renderedContent.value = marked.parse(data.content) as string
      
      // 解析统计数据
      stats.value = {
        total: data.stats.total || 0,
        successRate: data.stats.successRate || 0,
        avgTtft: data.stats.avgTtft || 0,
        avgTps: data.stats.avgTps || 0
      }
    }
  } catch (e) {
    console.error('加载报告失败:', e)
  } finally {
    loading.value = false
  }
}

// 切换模板
async function switchTemplate() {
  await loadReport()
}

// 导出操作
function exportPDF() {
  window.open(`/api/history/${props.groupId}/report/pdf?template=${selectedTemplate.value}`, '_blank')
}

async function exportMarkdown() {
  try {
    const res = await fetch(`/api/history/${props.groupId}/report/markdown?template=${selectedTemplate.value}`)
    const data = await res.json()
    if (data.success && data.content) {
      const filename = `report_${props.groupId}_${selectedTemplate.value}.md`
      const blob = new Blob([data.content], { type: 'text/markdown;charset=utf-8' })
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = filename
      link.click()
      URL.revokeObjectURL(url)
    }
  } catch (e) {
    console.error('导出 Markdown 失败:', e)
    showToast('导出 Markdown 失败，请重试', 'error')
  }
}

function exportExcel() {
  window.open(`/api/history/${props.groupId}/report/excel`, '_blank')
}

function copyLink() {
  const url = `${window.location.origin}/report/${props.groupId}`
  navigator.clipboard.writeText(url)
  showToast('分享链接已复制到剪贴板', 'success')
}

function close() {
  emit('close')
}

// 监听显示状态
watch(() => props.visible, (val) => {
  if (val) {
    loadTemplates()
    loadReport()
  }
})
</script>

<style lang="scss" scoped>
.report-preview-modal {
  width: 900px;
  max-width: 95vw;
  max-height: 90vh;
  background: white;
  border-radius: 12px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  border-bottom: 1px solid var(--gray-200);
  
  h3 {
    font-size: 18px;
    font-weight: 600;
  }
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.template-select {
  padding: 6px 10px;
  border: 1px solid var(--gray-300);
  background: white;
  border-radius: 6px;
  font-size: 13px;
  cursor: pointer;
  color: var(--gray-700);
  
  &:focus {
    border-color: var(--primary);
    outline: none;
  }
}

.btn-action {
  padding: 6px 12px;
  border: 1px solid var(--gray-300);
  background: white;
  border-radius: 6px;
  cursor: pointer;
  font-size: 13px;
  
  &:hover {
    border-color: var(--primary);
    color: var(--primary);
  }
}

.btn-close {
  width: 32px;
  height: 32px;
  border: none;
  background: var(--gray-100);
  border-radius: 6px;
  cursor: pointer;
  
  &:hover {
    background: var(--gray-200);
  }
}

.modal-body {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
}

.loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  height: 300px;
  color: var(--gray-500);
}

.spinner {
  width: 32px;
  height: 32px;
  border: 3px solid var(--gray-200);
  border-top-color: var(--primary);
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.report-content {
  line-height: 1.6;
  
  :deep(h1) {
    font-size: 24px;
    margin-bottom: 16px;
    padding-bottom: 8px;
    border-bottom: 2px solid var(--gray-300);
  }
  
  :deep(h2) {
    font-size: 18px;
    margin: 20px 0 12px;
    color: var(--gray-800);
  }
  
  :deep(h3) {
    font-size: 16px;
    margin: 16px 0 8px;
    color: var(--gray-700);
  }
  
  :deep(table) {
    width: 100%;
    border-collapse: collapse;
    margin: 16px 0;
    
    th, td {
      padding: 10px 12px;
      border: 1px solid var(--gray-200);
      text-align: left;
    }
    
    th {
      background: var(--gray-100);
      font-weight: 600;
    }
    
    tr:nth-child(even) {
      background: var(--gray-50);
    }
  }
  
  :deep(ul) {
    margin: 12px 0;
    padding-left: 24px;
    
    li {
      margin: 6px 0;
    }
  }
  
  :deep(hr) {
    border: none;
    border-top: 1px solid var(--gray-200);
    margin: 24px 0;
  }
}

.modal-footer {
  display: flex;
  gap: 24px;
  padding: 16px 20px;
  border-top: 1px solid var(--gray-200);
  background: var(--gray-50);
}

.stat-item {
  text-align: center;
}

.stat-label {
  display: block;
  font-size: 12px;
  color: var(--gray-500);
  margin-bottom: 4px;
}

.stat-value {
  font-size: 20px;
  font-weight: 600;
  color: var(--primary);
}

.rpm-toast {
  position: fixed;
  top: 24px;
  left: 50%;
  transform: translateX(-50%) translateY(-20px);
  padding: 10px 20px;
  border-radius: 8px;
  font-size: 0.85rem;
  opacity: 0;
  transition: all 0.25s;
  pointer-events: none;
  z-index: 10001;
  background: #10b981;
  color: #fff;
  box-shadow: 0 4px 16px rgba(0,0,0,0.3);
}

.rpm-toast.error { background: #dc2626; }
.rpm-toast.show { opacity: 1; transform: translateX(-50%) translateY(0); }
</style>
