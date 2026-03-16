<template>
  <div 
    class="log-panel" 
    :class="{ 
      minimized: minimized, 
      'drag-over': isDragging, 
      'resizing': isResizing,
      'panel-expanded': showAdvancedFilter
    }"
    :style="panelStyle"
  >
    <!-- 顶部调整大小手柄 -->
    <div class="log-resize-handle log-resize-handle-top" @mousedown.stop="$emit('resize-start-top', $event)"></div>
    <!-- 底部调整大小手柄 -->
    <div class="log-resize-handle log-resize-handle-bottom" @mousedown.stop="$emit('resize-start-bottom', $event)"></div>
    <!-- 左侧调整大小手柄 -->
    <div class="log-resize-handle log-resize-handle-left" @mousedown.stop="$emit('resize-start-left', $event)"></div>
    <!-- 右侧调整大小手柄 -->
    <div class="log-resize-handle log-resize-handle-right" @mousedown.stop="$emit('resize-start-right', $event)"></div>
    
    <!-- 面板拖拽头部 -->
    <div class="log-panel-header" @mousedown="$emit('panel-drag-start', $event)">
      <div class="log-header-left">
        <span class="log-title">📋 日志</span>
        <span class="log-count">
          ({{ filteredLogs.length }} 条{{ filteredLogs.length !== logs.length ? ' / ' + logs.length + ' 全部' : '' }})
        </span>
        <!-- 统计指示器 -->
        <div class="log-stats-mini" v-if="stats.total > 0">
          <span class="stat-error" :title="`错误: ${stats.error}`" v-if="stats.error > 0">✕{{ stats.error }}</span>
          <span class="stat-warning" :title="`警告: ${stats.warning}`" v-if="stats.warning > 0">⚠{{ stats.warning }}</span>
          <span class="stat-success" :title="`成功: ${stats.success}`" v-if="stats.success > 0">✓{{ stats.success }}</span>
          <span class="stat-running" :title="`进行中: ${stats.running}`" v-if="stats.running > 0">⟳{{ stats.running }}</span>
        </div>
      </div>
      <div class="log-header-right">
        <!-- 搜索框 -->
        <div class="log-search" :class="{ active: searchActive }">
          <input 
            type="text" 
            v-model="searchText" 
            placeholder="搜索日志..."
            @focus="searchActive = true"
            @blur="searchActive = false"
            @keydown.escape="searchText = ''"
          />
          <span v-if="searchText" class="log-search-clear" @click="searchText = ''">×</span>
        </div>
        <!-- 高级搜索切换 -->
        <button 
          class="log-action-btn" 
          :class="{ active: showAdvancedFilter }"
          @click="showAdvancedFilter = !showAdvancedFilter"
          title="高级搜索"
        >⚙</button>
        <!-- 过滤按钮 -->
        <div class="log-filter-group">
          <button 
            class="log-filter-btn" 
            :class="{ active: filter === 'all' }"
            @click="$emit('update:filter', 'all')"
            title="全部"
          >全部</button>
          <button 
            class="log-filter-btn" 
            :class="{ active: filter === 'error' }"
            @click="$emit('update:filter', 'error')"
            title="仅错误"
          >错误</button>
          <button 
            class="log-filter-btn" 
            :class="{ active: filter === 'warning' }"
            @click="$emit('update:filter', 'warning')"
            title="仅警告"
          >警告</button>
          <button 
            class="log-filter-btn" 
            :class="{ active: filter === 'running' }"
            @click="$emit('update:filter', 'running')"
            title="仅进行中"
          >进行中</button>
          <button 
            class="log-filter-btn" 
            :class="{ active: filter === 'success' }"
            @click="$emit('update:filter', 'success')"
            title="仅成功"
          >成功</button>
        </div>
        <!-- 自动滚动开关 -->
        <button 
          class="log-action-btn" 
          :class="{ active: autoScroll }"
          @click="$emit('toggle-auto-scroll')"
          :title="autoScroll ? '自动滚动: 开' : '自动滚动: 关'"
        >⬇</button>
        <!-- 清除日志 -->
        <button 
          class="log-action-btn" 
          @click="$emit('clear')"
          title="清除日志"
        >🗑</button>
        <!-- 导出日志 -->
        <button 
          class="log-action-btn" 
          @click="$emit('export')"
          title="导出日志"
        >📥</button>
        <!-- 最小化按钮 -->
        <button 
          class="log-action-btn log-minimize-btn" 
          @click="$emit('toggle-minimize')"
          :title="minimized ? '展开' : '最小化'"
        >
          {{ minimized ? '□' : '─' }}
        </button>
      </div>
    </div>
    
    <!-- 高级搜索面板 -->
    <div class="log-advanced-filter" v-if="showAdvancedFilter">
      <div class="filter-row">
        <label class="filter-label">
          <input type="checkbox" v-model="caseSensitive" />
          区分大小写
        </label>
        <label class="filter-label">
          <input type="checkbox" v-model="useRegex" />
          正则表达式
        </label>
        <button class="filter-btn" @click="clearTimeRange">清除时间筛选</button>
      </div>
    </div>
    
    <!-- 日志内容区域 -->
    <div
      class="log-area" 
      ref="logAreaRef"
      @scroll="handleScroll"
    >
      <!-- 滚动到顶部按钮 -->
      <button 
        v-if="showScrollTop" 
        class="scroll-top-btn"
        @click="scrollToTop"
        title="回到顶部"
      >↑</button>
      
      <div 
        v-for="(log, index) in filteredLogs" 
        :key="index" 
        class="log-item"
        :class="{ 
          'new-log': log.isNew, 
          'expanded': expandedLogIndex === index,
          [getLogLevelClass(log.tag)]: true 
        }"
        @click="handleLogClick(log, index)"
        @dblclick="expandLog(log, index)"
      >
        <span class="log-time" :title="log.fullTime">{{ log.time }}</span>
        <span class="log-tag" :class="[log.tag.toLowerCase(), getLogLevelClass(log.tag)]">{{ log.tag }}</span>
        <span class="log-msg" :class="{ 'log-msg-expanded': expandedLogIndex === index }">
          {{ expandedLogIndex === index ? log.msg : (log.msg.length > 100 ? log.msg.substring(0, 100) + '...' : log.msg) }}
        </span>
        <span v-if="log.isNew" class="log-new-badge">NEW</span>
        <button 
          v-if="expandedLogIndex !== index && log.msg.length > 100"
          class="log-expand-btn"
          @click.stop="expandLog(log, index)"
          title="展开"
        >⬇</button>
        <button 
          v-if="expandedLogIndex === index"
          class="log-copy-btn"
          @click.stop="copyLog(log)"
          title="复制"
        >📋</button>
      </div>
      <div v-if="filteredLogs.length === 0" class="log-empty">
        <span v-if="searchText">没有找到匹配的日志</span>
        <span v-else-if="filter !== 'all'">没有匹配的日志类型</span>
        <span v-else>暂无日志</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'

interface Log {
  time: string
  fullTime: string
  tag: string
  msg: string
  isNew: boolean
  level?: string
}

interface Props {
  logs: Log[]
  minimized: boolean
  x: number
  y: number
  width: number
  height: number
  filter: 'all' | 'error' | 'warning' | 'success' | 'running' | 'info'
  autoScroll: boolean
  isDragging?: boolean
  isResizing?: boolean
}

interface LogStats {
  total: number
  error: number
  warning: number
  success: number
  running: number
  info: number
}

const props = defineProps<Props>()

const emit = defineEmits<{
  'update:filter': [value: 'all' | 'error' | 'warning' | 'success' | 'running' | 'info']
  'toggle-auto-scroll': []
  'toggle-minimize': []
  'clear': []
  'export': []
  copy: [log: Log]
  'panel-drag-start': [event: MouseEvent]
  'resize-start-top': [event: MouseEvent]
  'resize-start-bottom': [event: MouseEvent]
  'resize-start-left': [event: MouseEvent]
  'resize-start-right': [event: MouseEvent]
}>()

const searchText = ref('')
const searchActive = ref(false)
const logAreaRef = ref<HTMLElement | null>(null)

// 高级搜索状态
const showAdvancedFilter = ref(false)
const caseSensitive = ref(false)
const useRegex = ref(false)

// 展开/折叠状态
const expandedLogIndex = ref<number | null>(null)

// 滚动到顶部按钮
const showScrollTop = ref(false)

// 日志级别映射
const levelMap: Record<string, string> = {
  'error': 'error',
  'err': 'error',
  'stop': 'warning',
  'warning': 'warning',
  'warn': 'warning',
  'done': 'success',
  'finish': 'success',
  'complete': 'success',
  'summary': 'success',
  'round': 'running',
  'chunk': 'running',
  'start': 'info',
  'retry': 'info',
  'info': 'info'
}

// 计算日志统计
const stats = computed<LogStats>(() => {
  const result: LogStats = {
    total: props.logs.length,
    error: 0,
    warning: 0,
    success: 0,
    running: 0,
    info: 0
  }
  
  props.logs.forEach(log => {
    const level = getLogLevel(log.tag)
    switch (level) {
      case 'error':
        result.error++
        break
      case 'warning':
        result.warning++
        break
      case 'success':
        result.success++
        break
      case 'running':
        result.running++
        break
      case 'info':
        result.info++
        break
    }
  })
  
  return result
})

// 过滤后的日志
const filteredLogs = computed(() => {
  let result = props.logs
  
  // 按过滤类型筛选
  if (props.filter !== 'all') {
    result = result.filter(log => {
      const level = getLogLevel(log.tag)
      return level === props.filter
    })
  }
  
  // 按搜索文本筛选
  if (searchText.value) {
    const search = caseSensitive.value ? searchText.value : searchText.value.toLowerCase()
    
    result = result.filter(log => {
      const msg = caseSensitive.value ? log.msg : log.msg.toLowerCase()
      const tag = caseSensitive.value ? log.tag : log.tag.toLowerCase()
      
      if (useRegex.value) {
        try {
          const regex = new RegExp(search, caseSensitive.value ? '' : 'i')
          return regex.test(log.msg) || regex.test(log.tag)
        } catch {
          // 正则表达式无效，回退到普通搜索
          return msg.includes(search) || tag.includes(search)
        }
      }
      
      return msg.includes(search) || tag.includes(search)
    })
  }
  
  return result
})

const panelStyle = computed(() => ({
  position: 'fixed',
  left: props.x + 'px',
  top: props.y + 'px',
  width: props.width + 'px',
  height: props.minimized ? 'auto' : props.height + 'px',
  zIndex: 50,
  boxShadow: '0 4px 20px rgba(0, 0, 0, 0.15)',
  borderRadius: props.minimized ? '50%' : '12px'
}))

// 获取日志级别
function getLogLevel(tag: string): string {
  const tagLower = tag.toLowerCase()
  return levelMap[tagLower] || 'default'
}

function getLogLevelClass(tag: string): string {
  const level = getLogLevel(tag)
  return `level-${level}`
}

// 处理日志点击
function handleLogClick(log: Log, index: number) {
  emit('copy', log)
}

// 展开/折叠日志
function expandLog(log: Log, index: number) {
  if (expandedLogIndex.value === index) {
    expandedLogIndex.value = null
  } else {
    expandedLogIndex.value = index
  }
}

// 复制日志
function copyLog(log: Log) {
  const text = `[${log.fullTime}] [${log.tag}] ${log.msg}`
  navigator.clipboard.writeText(text)
}

// 滚动到顶部
function scrollToTop() {
  if (logAreaRef.value) {
    logAreaRef.value.scrollTop = 0
  }
}

// 滚动事件处理
function handleScroll() {
  if (logAreaRef.value) {
    // 当滚动超过 100px 时显示滚动到顶部按钮
    showScrollTop.value = logAreaRef.value.scrollTop > 100
  }
}

// 清除时间筛选
function clearTimeRange() {
  // 时间范围功能可以后续扩展
}

// 同步搜索文本
watch(searchText, (val) => {
  // 可以选择是否需要同步到父组件
})
</script>

<style lang="scss" scoped>
// 变量定义
$primary: #2563eb;
$primary-dim: rgba(37, 99, 235, 0.1);
$gray-50: #f9fafb;
$gray-100: #f3f4f6;
$gray-200: #e5e7eb;
$gray-300: #d1d5db;
$gray-400: #9ca3af;
$gray-500: #6b7280;
$gray-600: #4b5563;
$gray-700: #374151;
$gray-800: #1f2937;
$gray-900: #111827;
$white: #ffffff;
$accent-red: #ef4444;
$accent-orange: #f97316;
$accent-green: #22c55e;
$accent-blue: #3b82f6;
$accent-purple: #8b5cf6;

.log-panel {
  background: var(--white);
  border: 1px solid var(--gray-200);
  border-radius: 12px;
  overflow: visible;
  display: flex;
  flex-direction: column;
  transition: box-shadow 0.2s ease;
  
  &.minimized {
    width: 80px !important;
    height: 80px !important;
    min-height: 80px !important;
    border-radius: 50% !important;
    cursor: pointer;
    
    .log-panel-header {
      padding: 20px;
      justify-content: center;
      min-height: 80px;
    }
    
    .log-header-left, .log-header-right {
      flex-direction: column;
      gap: 4px;
    }
    
    .log-header-right {
      display: none;
    }
    
    .log-area, .log-resize-handle {
      display: none;
    }
    
    .log-panel-header::after {
      content: '📋';
      font-size: 24px;
    }
  }
  
  &:active {
    cursor: moving;
  }
  
  &.drag-over {
    box-shadow: 0 8px 32px rgba(37, 99, 235, 0.25), 0 0 0 2px var(--primary);
  }
  
  &.resizing {
    box-shadow: 0 8px 32px rgba(37, 99, 235, 0.25), 0 0 0 2px var(--primary);
    cursor: nwse-resize;
  }
}

.log-resize-handle {
  position: absolute;
  z-index: 20;
  background: transparent;
  transition: background 0.15s ease;
  
  &:hover, &:active {
    background: rgba(37, 99, 235, 0.15);
  }
}

.log-resize-handle-top {
  top: -4px;
  left: 12px;
  right: 12px;
  height: 8px;
  cursor: n-resize;
  border-radius: 4px 4px 0 0;
}

.log-resize-handle-bottom {
  bottom: -4px;
  left: 12px;
  right: 12px;
  height: 8px;
  cursor: s-resize;
  border-radius: 0 0 4px 4px;
}

.log-resize-handle-left {
  left: -6px;
  top: 44px;
  bottom: 40px;
  width: 14px;
  cursor: w-resize;
  border-radius: 6px 0 0 6px;
}

.log-resize-handle-right {
  right: -6px;
  top: 44px;
  bottom: 40px;
  width: 14px;
  cursor: e-resize;
  border-radius: 0 6px 6px 0;
}

.log-panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 16px;
  background: var(--gray-50);
  border-bottom: 1px solid var(--gray-200);
  min-height: 44px;
  box-sizing: border-box;
  flex-shrink: 0;
  cursor: move;
  user-select: none;
  
  &:hover {
    background: var(--gray-100);
  }
}

.log-header-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.log-header-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.log-title {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--gray-800);
}

.log-count {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.65rem;
  color: var(--gray-500);
}

// 统计指示器
.log-stats-mini {
  display: flex;
  gap: 6px;
  margin-left: 8px;
  
  span {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.55rem;
    padding: 2px 6px;
    border-radius: 3px;
    cursor: default;
  }
  
  .stat-error {
    background: rgba(239, 68, 68, 0.15);
    color: #ef4444;
  }
  
  .stat-warning {
    background: rgba(245, 158, 11, 0.15);
    color: #f59e0b;
  }
  
  .stat-success {
    background: rgba(34, 197, 94, 0.15);
    color: #22c55e;
  }
  
  .stat-running {
    background: rgba(59, 130, 246, 0.15);
    color: #3b82f6;
  }
}

// 高级搜索面板
.log-advanced-filter {
  background: var(--gray-50);
  border-bottom: 1px solid var(--gray-200);
  padding: 8px 16px;
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  
  .filter-row {
    display: flex;
    align-items: center;
    gap: 12px;
  }
  
  .filter-label {
    display: flex;
    align-items: center;
    gap: 4px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.6rem;
    color: var(--gray-600);
    cursor: pointer;
    
    input[type="checkbox"] {
      cursor: pointer;
    }
  }
  
  .filter-btn {
    padding: 4px 8px;
    border: 1px solid var(--gray-300);
    border-radius: 4px;
    background: var(--white);
    color: var(--gray-600);
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.55rem;
    cursor: pointer;
    transition: all 0.15s;
    
    &:hover {
      border-color: var(--primary);
      color: var(--primary);
    }
  }
}

.log-search {
  position: relative;
  display: flex;
  align-items: center;
  
  input {
    width: 120px;
    padding: 4px 24px 4px 8px;
    border: 1px solid var(--gray-300);
    border-radius: 4px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.65rem;
    background: var(--white);
    color: var(--gray-900);
    transition: all 0.2s ease;
    
    &::placeholder {
      color: var(--gray-400);
    }
    
    &:focus {
      outline: none;
      border-color: var(--primary);
      width: 160px;
      box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.1);
    }
  }
  
  &.active input {
    border-color: var(--primary);
  }
  
  .log-search-clear {
    position: absolute;
    right: 6px;
    cursor: pointer;
    color: var(--gray-400);
    font-size: 0.75rem;
    padding: 2px;
    
    &:hover {
      color: var(--gray-700);
    }
  }
}

.log-filter-group {
  display: flex;
  gap: 4px;
}

.log-filter-btn {
  padding: 4px 8px;
  border: 1px solid var(--gray-300);
  border-radius: 4px;
  background: var(--white);
  color: var(--gray-600);
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.6rem;
  cursor: pointer;
  transition: all 0.15s ease;
  
  &:hover {
    border-color: var(--gray-400);
    color: var(--gray-700);
  }
  
  &.active {
    background: var(--primary);
    border-color: var(--primary);
    color: var(--white);
  }
}

.log-action-btn {
  width: 28px;
  height: 28px;
  padding: 0;
  border: 1px solid var(--gray-300);
  border-radius: 4px;
  background: var(--white);
  color: var(--gray-600);
  font-size: 0.7rem;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s ease;
  
  &:hover {
    border-color: var(--primary);
    color: var(--primary);
    background: var(--gray-50);
  }
  
  &.active {
    background: var(--primary-dim);
    border-color: var(--primary);
    color: var(--primary);
  }
}

.log-area {
  position: relative;
  background: linear-gradient(180deg, var(--gray-50) 0%, var(--gray-100) 100%);
  border-top: 1px solid var(--gray-200);
  padding: 10px 16px;
  overflow-x: auto;
  overflow-y: auto;
  display: flex;
  flex-wrap: wrap;
  align-content: flex-start;
  gap: 8px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.7rem;
}

.log-item {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--gray-400);
  white-space: nowrap;
  flex-shrink: 0;
  cursor: pointer;
  transition: all 0.15s ease;
  padding: 4px 8px;
  border-radius: 4px;
  border: 1px solid transparent;
  position: relative;
  
  &:hover {
    background: var(--gray-200);
    border-color: var(--gray-300);
    
    .log-expand-btn, .log-copy-btn {
      opacity: 1;
    }
  }
  
  &.expanded {
    white-space: normal;
    flex-wrap: wrap;
    background: var(--gray-100);
    border-color: var(--gray-300);
    
    .log-msg {
      white-space: pre-wrap;
      word-break: break-word;
      max-width: 100%;
    }
  }
  
  &.level-error {
    .log-tag {
      background: rgba(239, 68, 68, 0.15);
      color: #ef4444;
    }
    .log-msg {
      color: #ef4444;
    }
  }
  
  &.level-success {
    .log-tag {
      background: rgba(34, 197, 94, 0.15);
      color: #22c55e;
    }
  }
  
  &.level-running {
    .log-tag {
      background: rgba(59, 130, 246, 0.15);
      color: #3b82f6;
    }
  }
  
  &.new-log {
    background: rgba(59, 130, 246, 0.08);
    border-color: rgba(59, 130, 246, 0.2);
    animation: logFadeIn 0.3s ease;
  }
}

// 展开/复制按钮
.log-expand-btn, .log-copy-btn {
  opacity: 0;
  padding: 2px 6px;
  border: none;
  background: var(--gray-300);
  color: var(--gray-600);
  border-radius: 3px;
  font-size: 0.6rem;
  cursor: pointer;
  transition: all 0.15s;
  margin-left: auto;
  
  &:hover {
    background: var(--primary);
    color: var(--white);
  }
}

.log-copy-btn {
  margin-left: 4px;
}

// 滚动到顶部按钮
.scroll-top-btn {
  position: absolute;
  bottom: 16px;
  right: 16px;
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: var(--primary);
  color: var(--white);
  border: none;
  font-size: 1rem;
  cursor: pointer;
  box-shadow: 0 2px 8px rgba(37, 99, 235, 0.4);
  transition: all 0.2s;
  z-index: 10;
  
  &:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(37, 99, 235, 0.5);
  }
}

@keyframes logFadeIn {
  from {
    opacity: 0;
    transform: translateX(-10px);
  }
  to {
    opacity: 1;
    transform: translateX(0);
  }
}

.log-time {
  color: var(--gray-600);
  flex-shrink: 0;
}

.log-tag {
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 0.65rem;
  background: var(--gray-700);
  color: var(--gray-300);
  flex-shrink: 0;
}

.log-msg {
  color: var(--gray-700);
  max-width: 500px;
  overflow: hidden;
  text-overflow: ellipsis;
  flex: 1;
  
  &.log-msg-expanded {
    white-space: pre-wrap;
    word-break: break-word;
  }
}

.log-new-badge {
  padding: 1px 5px;
  border-radius: 3px;
  background: var(--primary);
  color: var(--white);
  font-size: 0.5rem;
  font-weight: 600;
  animation: blink 1s infinite;
  flex-shrink: 0;
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.log-empty {
  width: 100%;
  padding: 20px;
  text-align: center;
  color: var(--gray-500);
  font-size: 0.75rem;
  font-family: 'JetBrains Mono', monospace;
}
</style>