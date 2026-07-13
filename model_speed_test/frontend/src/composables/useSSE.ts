import { ref, onUnmounted } from 'vue'

export interface SSEEvent {
  type: string
  data: any
}

const MAX_RECONNECT_ATTEMPTS = 5
const BASE_DELAY = 1000 // 1s
const MAX_DELAY = 30000 // 30s

export function useSSE() {
  const connected = ref(false)
  const status = ref('--')
  let eventSource: EventSource | null = null
  let reconnectAttempts = 0
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null

  function connect(onMessage: (event: SSEEvent) => void) {
    disconnect()

    eventSource = new EventSource('/events')

    eventSource.onopen = () => {
      reconnectAttempts = 0
      connected.value = true
      status.value = 'OK'
    }

    eventSource.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data)
        onMessage({ type: data.type, data: data.data })
      } catch (err) {
        console.error('[SSE] 消息解析失败:', err)
        console.error('[SSE] 原始数据:', e.data)
        status.value = '解析错误'
      }
    }

    eventSource.onerror = () => {
      if (eventSource) {
        eventSource.close()
        eventSource = null
      }
      connected.value = false

      if (reconnectAttempts < MAX_RECONNECT_ATTEMPTS) {
        reconnectAttempts++
        // 指数退避: 2s, 4s, 8s, 16s, 30s
        const delay = Math.min(
          BASE_DELAY * Math.pow(2, reconnectAttempts),
          MAX_DELAY
        )
        status.value = `重连中 (${reconnectAttempts}/${MAX_RECONNECT_ATTEMPTS})`
        console.warn(`[SSE] 连接断开，${delay / 1000}s 后重试 (${reconnectAttempts}/${MAX_RECONNECT_ATTEMPTS})`)
        reconnectTimer = setTimeout(() => {
          if (!connected.value) {
            connect(onMessage)
          }
        }, delay)
      } else {
        status.value = '连接失败，请刷新页面'
        console.error('[SSE] 已达最大重试次数 (${MAX_RECONNECT_ATTEMPTS})，停止重连')
      }
    }
  }

  function disconnect() {
    if (reconnectTimer) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
    if (eventSource) {
      eventSource.close()
      eventSource = null
    }
    reconnectAttempts = 0
    connected.value = false
    status.value = '--'
  }

  onUnmounted(() => {
    disconnect()
  })

  return {
    connected,
    status,
    connect,
    disconnect
  }
}