import { ref, onUnmounted } from 'vue'

export interface SSEEvent {
  type: string
  data: any
}

export function useSSE() {
  const connected = ref(false)
  const status = ref('--')
  let eventSource: EventSource | null = null
  
  function connect(onMessage: (event: SSEEvent) => void) {
    disconnect()
    
    eventSource = new EventSource('/events')
    
    eventSource.onopen = () => {
      connected.value = true
      status.value = 'OK'
    }
    
    eventSource.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data)
        onMessage({ type: data.type, data: data.data })
      } catch (err) {
        console.error('SSE parse error:', err)
      }
    }
    
    eventSource.onerror = () => {
      connected.value = false
      status.value = 'RETRY'
      // 自动重连
      setTimeout(() => {
        if (!connected.value) {
          connect(onMessage)
        }
      }, 3000)
    }
  }
  
  function disconnect() {
    if (eventSource) {
      eventSource.close()
      eventSource = null
    }
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