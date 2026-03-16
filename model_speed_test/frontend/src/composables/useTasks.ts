import { ref, computed, reactive } from 'vue'

export interface SubTask {
  name: string
  output: string
  status: string
  metrics: any
  prompt?: string
  error?: string
}

export interface Task {
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
  avgAnswerSpeed?: string
  avgThinkTokens?: string
  avgAnswerTokens?: string
  expanded?: boolean
}

export interface CardPosition {
  order: number
  width: number
  height: number
}

// 选择状态
const selectedModels = ref<Set<string>>(new Set())
const selectedCases = ref<Set<string>>(new Set())

// 卡片拖拽状态
const cardDragState = reactive({
  isDragging: false,
  draggingCardId: null as string | null,
  startX: 0,
  startY: 0,
  startIndex: -1,
  currentIndex: -1
})

// 卡片尺寸调整状态
const cardResizeState = reactive({
  isResizing: false,
  resizingCardId: null as string | null,
  startX: 0,
  startY: 0,
  startWidth: 0,
  startHeight: 0
})

const MIN_CARD_WIDTH = 280
const MAX_CARD_WIDTH = 600
const MIN_CARD_HEIGHT = 180
const MAX_CARD_HEIGHT = 500

export function useTasks() {
  const tasks = ref<Record<string, Task>>({})
  const cardPositions = ref<Record<string, CardPosition>>({})
  const taskOrder = ref<string[]>([])
  
  const taskCount = computed(() => Object.keys(tasks.value).length)
  
  // 选择相关的函数
  function toggleModel(name: string) {
    if (selectedModels.value.has(name)) {
      selectedModels.value.delete(name)
    } else {
      selectedModels.value.add(name)
    }
    localStorage.setItem('selectedModels', JSON.stringify([...selectedModels.value]))
  }
  
  function toggleCase(id: string) {
    if (selectedCases.value.has(id)) {
      selectedCases.value.delete(id)
    } else {
      selectedCases.value.add(id)
    }
    localStorage.setItem('selectedCases', JSON.stringify([...selectedCases.value]))
  }
  
  function selectAllModels(models: any[]) {
    if (selectedModels.value.size === models.length) {
      selectedModels.value.clear()
    } else {
      models.forEach((m: any) => selectedModels.value.add(m.name))
    }
    localStorage.setItem('selectedModels', JSON.stringify([...selectedModels.value]))
  }
  
  function selectAllCases(cases: any[]) {
    if (selectedCases.value.size === cases.length) {
      selectedCases.value.clear()
    } else {
      cases.forEach((c: any) => selectedCases.value.add(c.id))
    }
    localStorage.setItem('selectedCases', JSON.stringify([...selectedCases.value]))
  }
  
  function getTaskId(modelName: string, caseName: string): string {
    return `${modelName}__${caseName}`
  }
  
  function getSubTaskId(modelName: string, caseName: string, round: number): string {
    return `${modelName}__${caseName}__${round}`
  }
  
  function getSubTaskIndex(task: Task, subId: string): number {
    const keys = Object.keys(task.sub_tasks)
    return keys.indexOf(subId)
  }
  
  function createTask(modelName: string, caseName: string, totalRounds: number = 10) {
    const taskId = getTaskId(modelName, caseName)
    const existingTask = tasks.value[taskId]
    
    tasks.value[taskId] = {
      model_name: modelName,
      case_name: caseName,
      progress: 0,
      status: 'running',
      current_round: 0,
      total_rounds: totalRounds,
      sub_tasks: existingTask ? existingTask.sub_tasks : {}
    }
    
    // 预创建所有轮次
    for (let r = 1; r <= totalRounds; r++) {
      const subId = getSubTaskId(modelName, caseName, r)
      if (!tasks.value[taskId].sub_tasks[subId]) {
        tasks.value[taskId].sub_tasks[subId] = {
          name: `Round ${r}/${totalRounds}`,
          output: '',
          status: 'pending',
          metrics: {}
        }
      } else {
        tasks.value[taskId].sub_tasks[subId].name = `Round ${r}/${totalRounds}`
      }
    }
    
    // 初始化卡片位置
    initCardPosition(taskId)
    
    return taskId
  }
  
  function initCardPosition(taskId: string) {
    if (!cardPositions.value[taskId]) {
      const order = taskOrder.value.length
      cardPositions.value[taskId] = {
        order: order,
        width: 320,
        height: 180
      }
      taskOrder.value.push(taskId)
    }
  }
  
  function updateSubTask(modelName: string, caseName: string, round: number, totalRounds: number, status: string = 'running') {
    const taskId = getTaskId(modelName, caseName)
    const subId = getSubTaskId(modelName, caseName, round)
    
    if (!tasks.value[taskId]) {
      tasks.value[taskId] = {
        model_name: modelName,
        case_name: caseName,
        progress: 0,
        status: 'running',
        current_round: round,
        total_rounds: totalRounds,
        sub_tasks: {}
      }
      
      for (let r = 1; r <= totalRounds; r++) {
        const sid = getSubTaskId(modelName, caseName, r)
        tasks.value[taskId].sub_tasks[sid] = {
          name: `Round ${r}/${totalRounds}`,
          output: '',
          status: r === round ? status : 'pending',
          metrics: {}
        }
      }
    } else {
      tasks.value[taskId].total_rounds = totalRounds
      
      if (!tasks.value[taskId].sub_tasks[subId]) {
        tasks.value[taskId].sub_tasks[subId] = {
          name: `Round ${round}/${totalRounds}`,
          output: '',
          status: status,
          metrics: {}
        }
      } else {
        tasks.value[taskId].sub_tasks[subId].status = status
      }
    }
    
    tasks.value[taskId].current_round = round
    tasks.value[taskId].progress = Math.round((round / totalRounds) * 100)
    
    const subTasks = tasks.value[taskId].sub_tasks
    const allDone = Object.values(subTasks).every(t => t.status === 'done' || t.status === 'error')
    if (allDone && Object.keys(subTasks).length >= totalRounds) {
      tasks.value[taskId].status = 'done'
      calculateAverages(taskId)
    } else {
      tasks.value[taskId].status = 'running'
    }
    
    return subId
  }
  
  function calculateAverages(taskId: string) {
    const task = tasks.value[taskId]
    if (!task) return
    
    const subTasks = Object.values(task.sub_tasks)
    
    const doneTasks = subTasks.filter(st => {
      if (st.status !== 'done') return false
      if (!st.metrics) return false
      const m = st.metrics
      return (m.ttft && m.ttft !== '--') || (m.speed && m.speed !== '--')
    })
    
    if (doneTasks.length === 0) return
    
    let ttftSum = 0, tpftSum = 0, tokenSum = 0, speedSum = 0
    let ttftCount = 0, tpftCount = 0, tokenCount = 0, speedCount = 0
    
    let thinkTokenSum = 0, answerTokenSum = 0, answerSpeedSum = 0
    let thinkTokenCount = 0, answerTokenCount = 0, answerSpeedCount = 0
    
    doneTasks.forEach(t => {
      const m = t.metrics
      if (m.ttft && m.ttft !== '--') {
        const v = parseFloat(m.ttft)
        if (!isNaN(v)) { ttftSum += v; ttftCount++ }
      }
      if (m.tpft && m.tpft !== '--') {
        const v = parseFloat(m.tpft)
        if (!isNaN(v)) { tpftSum += v; tpftCount++ }
      }
      if (m.tokens && m.tokens !== '--') {
        const v = parseFloat(m.tokens)
        if (!isNaN(v)) { tokenSum += v; tokenCount++ }
      }
      if (m.speed && m.speed !== '--') {
        const v = parseFloat(m.speed)
        if (!isNaN(v)) { speedSum += v; speedCount++ }
      }
      if (m.thinkTokens && m.thinkTokens !== '--') {
        const v = parseFloat(m.thinkTokens)
        if (!isNaN(v)) { thinkTokenSum += v; thinkTokenCount++ }
      }
      if (m.answerTokens && m.answerTokens !== '--') {
        const v = parseFloat(m.answerTokens)
        if (!isNaN(v)) { answerTokenSum += v; answerTokenCount++ }
      }
      if (m.answerSpeed && m.answerSpeed !== '--') {
        const v = parseFloat(m.answerSpeed)
        if (!isNaN(v)) { answerSpeedSum += v; answerSpeedCount++ }
      }
    })
    
    task.avgTtft = ttftCount > 0 ? (ttftSum / ttftCount).toFixed(3) : '--'
    task.avgTpft = tpftCount > 0 ? (tpftSum / tpftCount).toFixed(3) : '--'
    task.avgTokens = tokenCount > 0 ? Math.round(tokenSum / tokenCount) : '--'
    task.avgSpeed = speedCount > 0 ? (speedSum / speedCount).toFixed(1) : '--'
    task.avgThinkTokens = thinkTokenCount > 0 ? Math.round(thinkTokenSum / thinkTokenCount) : '--'
    task.avgAnswerTokens = answerTokenCount > 0 ? Math.round(answerTokenSum / answerTokenCount) : '--'
    task.avgAnswerSpeed = answerSpeedCount > 0 ? (answerSpeedSum / answerSpeedCount).toFixed(1) : '--'
  }
  
  function stopTask(taskId: string) {
    const task = tasks.value[taskId]
    if (!task) return
    
    Object.values(task.sub_tasks).forEach(subTask => {
      if (subTask.status === 'running') {
        subTask.status = 'error'
      }
    })
    
    task.status = 'stopped'
  }
  
  function retryTask(taskId: string) {
    const task = tasks.value[taskId]
    if (!task) return
    
    const totalRounds = task.total_rounds
    for (let r = 1; r <= totalRounds; r++) {
      const subId = getSubTaskId(task.model_name, task.case_name, r)
      if (task.sub_tasks[subId]) {
        task.sub_tasks[subId] = {
          name: `Round ${r}/${totalRounds}`,
          output: '',
          status: 'pending',
          metrics: {}
        }
      }
    }
    
    task.status = 'running'
    task.progress = 0
    task.current_round = 0
    task.avgTtft = undefined
    task.avgTpft = undefined
    task.avgTokens = undefined
    task.avgSpeed = undefined
    task.avgAnswerSpeed = undefined
    task.avgThinkTokens = undefined
    task.avgAnswerTokens = undefined
  }
  
  function clearTasks() {
    tasks.value = {}
  }
  
  function reorderTasks(fromIndex: number, toIndex: number) {
    const [removed] = taskOrder.value.splice(fromIndex, 1)
    taskOrder.value.splice(toIndex, 0, removed)
    
    taskOrder.value.forEach((taskId, index) => {
      if (cardPositions.value[taskId]) {
        cardPositions.value[taskId].order = index
      }
    })
  }
  
  function saveCardPositions() {
    localStorage.setItem('taskCardPositions', JSON.stringify(cardPositions.value))
    localStorage.setItem('taskCardOrder', JSON.stringify(taskOrder.value))
  }
  
  function loadCardPositions() {
    try {
      const savedPositions = localStorage.getItem('taskCardPositions')
      const savedOrder = localStorage.getItem('taskCardOrder')
      
      if (savedPositions) {
        cardPositions.value = JSON.parse(savedPositions)
      }
      if (savedOrder) {
        taskOrder.value = JSON.parse(savedOrder)
      }
    } catch (e) {
      console.error('Failed to load card positions:', e)
    }
  }
  
  // 计算属性
  function doneCount(task: Task): number {
    return Object.values(task.sub_tasks || {}).filter(t => t.status === 'done').length
  }
  
  function runningCount(task: Task): number {
    return Object.values(task.sub_tasks || {}).filter(t => t.status === 'running').length
  }
  
  function errorCount(task: Task): number {
    return Object.values(task.sub_tasks || {}).filter(t => t.status === 'error').length
  }
  
  function getCardStyle(taskId: string): Record<string, string> {
    const pos = cardPositions.value[taskId]
    if (!pos) return {}
    
    const style: Record<string, string> = {}
    
    if (pos.width && pos.width !== 320) {
      style.width = pos.width + 'px'
    }
    if (pos.height && pos.height !== 180) {
      style.minHeight = pos.height + 'px'
    }
    
    return style
  }
  
  return {
    // 状态
    tasks,
    cardPositions,
    taskOrder,
    taskCount,
    selectedModels,
    selectedCases,
    cardDragState,
    cardResizeState,
    // 选择函数
    toggleModel,
    toggleCase,
    selectAllModels,
    selectAllCases,
    // 任务函数
    getTaskId,
    getSubTaskId,
    getSubTaskIndex,
    createTask,
    updateSubTask,
    calculateAverages,
    stopTask,
    retryTask,
    clearTasks,
    // 排序和位置
    reorderTasks,
    saveCardPositions,
    loadCardPositions,
    initCardPosition,
    // 计算属性
    doneCount,
    runningCount,
    errorCount,
    getCardStyle
  }
}
