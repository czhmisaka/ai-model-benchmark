import { ref, computed, nextTick, watch } from 'vue'

export interface Log {
  time: string
  fullTime: string
  tag: string
  msg: string
  isNew: boolean
  level?: LogLevel
}

export type LogLevel = 'error' | 'warning' | 'success' | 'info' | 'running' | 'debug' | 'default'

export type FilterType = 'all' | 'error' | 'warning' | 'success' | 'running' | 'info'

export interface LogStats {
  total: number
  error: number
  warning: number
  success: number
  running: number
  info: number
}

export function useLogs() {
  const logs = ref<Log[]>([])
  const searchText = ref('')
  const filter = ref<FilterType>('all')
  const autoScroll = ref(true)
  const logAreaRef = ref<HTMLElement | null>(null)
  const logSearchActive = ref(false)
  const logMinimized = ref(false)
  
  // 新增：高级过滤选项
  const caseSensitive = ref(false)
  const useRegex = ref(false)
  const timeRange = ref<{ start?: Date; end?: Date }>({})
  
  // 日志级别映射
  const levelMap: Record<string, LogLevel> = {
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
    'info': 'info',
    'debug': 'debug',
    'system': 'default',
    'model': 'default',
    'case': 'default'
  }
  
  // 获取日志级别
  function getLogLevel(tag: string): LogLevel {
    const tagLower = tag.toLowerCase()
    return levelMap[tagLower] || 'default'
  }
  
  // 日志统计
  const logStats = computed<LogStats>(() => {
    const stats: LogStats = {
      total: logs.value.length,
      error: 0,
      warning: 0,
      success: 0,
      running: 0,
      info: 0
    }
    
    logs.value.forEach(log => {
      const level = log.level || getLogLevel(log.tag)
      switch (level) {
        case 'error':
          stats.error++
          break
        case 'warning':
          stats.warning++
          break
        case 'success':
          stats.success++
          break
        case 'running':
          stats.running++
          break
        case 'info':
          stats.info++
          break
      }
    })
    
    return stats
  })
  
  // 过滤后的日志
  const filteredLogs = computed(() => {
    let result = logs.value
    
    // 按过滤类型筛选
    if (filter.value !== 'all') {
      result = result.filter(log => {
        const level = log.level || getLogLevel(log.tag)
        return level === filter.value
      })
    }
    
    // 按时间范围筛选
    if (timeRange.value.start || timeRange.value.end) {
      result = result.filter(log => {
        const logTime = new Date(log.fullTime)
        if (timeRange.value.start && logTime < timeRange.value.start) return false
        if (timeRange.value.end && logTime > timeRange.value.end) return false
        return true
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
  
  // 获取日志级别样式类
  function getLogLevelClass(tag: string): string {
    const level = getLogLevel(tag)
    return `level-${level}`
  }
  
  // 添加日志
  function addLog(time: string, tag: string, msg: string) {
    const now = new Date()
    const fullTime = now.toISOString()
    const level = getLogLevel(tag)
    
    logs.value.push({ 
      time, 
      fullTime, 
      tag, 
      msg, 
      isNew: true,
      level 
    })
    
    // 限制日志数量，保留最新的 500 条
    if (logs.value.length > 500) {
      logs.value = logs.value.slice(-500)
    }
    
    // 标记旧日志为非新
    if (logs.value.length > 1) {
      logs.value[logs.value.length - 2].isNew = false
    }
    
    // 自动滚动
    scrollToBottom()
  }
  
  // 清除日志
  function clearLogs() {
    logs.value = []
  }
  
  // 导出日志
  function exportLogs(): string {
    return logs.value
      .map(log => `[${log.fullTime}] [${log.tag}] ${log.msg}`)
      .join('\n')
  }
  
  // 复制单条日志
  function copyLog(log: Log): string {
    return `[${log.fullTime}] [${log.tag}] ${log.msg}`
  }
  
  // 滚动到底部
  function scrollToBottom() {
    if (autoScroll.value && logAreaRef.value) {
      nextTick(() => {
        logAreaRef.value!.scrollTop = logAreaRef.value!.scrollHeight
      })
    }
  }
  
  // 设置时间范围
  function setTimeRange(start?: Date, end?: Date) {
    timeRange.value = { start, end }
  }
  
  // 清除时间范围
  function clearTimeRange() {
    timeRange.value = {}
  }
  
  // 标记所有日志为已读
  function markAllAsRead() {
    logs.value.forEach(log => {
      log.isNew = false
    })
  }
  
  // 获取最新错误日志
  function getRecentErrors(count: number = 10): Log[] {
    return logs.value
      .filter(log => (log.level || getLogLevel(log.tag)) === 'error')
      .slice(-count)
      .reverse()
  }
  
  return {
    logs,
    searchText,
    filter,
    autoScroll,
    logAreaRef,
    logSearchActive,
    logMinimized,
    caseSensitive,
    useRegex,
    timeRange,
    filteredLogs,
    logStats,
    getLogLevelClass,
    getLogLevel,
    addLog,
    clearLogs,
    exportLogs,
    copyLog,
    scrollToBottom,
    setTimeRange,
    clearTimeRange,
    markAllAsRead,
    getRecentErrors
  }
}