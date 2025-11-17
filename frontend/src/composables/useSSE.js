import { ref, onMounted, onUnmounted } from 'vue'

export function useSSE(url, onMessage) {
  const eventSource = ref(null)
  const connected = ref(false)
  const error = ref(null)

  const connect = () => {
    try {
      eventSource.value = new EventSource(url)

      eventSource.value.onopen = () => {
        connected.value = true
        error.value = null
        console.log('SSE connected to', url)
      }

      eventSource.value.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          onMessage(data)
        } catch (err) {
          console.error('Failed to parse SSE message:', err)
        }
      }

      eventSource.value.onerror = (err) => {
        connected.value = false
        error.value = 'Connection lost. Reconnecting...'
        console.error('SSE error:', err)

        // Auto-reconnect after 3 seconds
        setTimeout(() => {
          if (eventSource.value) {
            eventSource.value.close()
            connect()
          }
        }, 3000)
      }
    } catch (err) {
      error.value = err.message
      console.error('Failed to create SSE connection:', err)
    }
  }

  const disconnect = () => {
    if (eventSource.value) {
      eventSource.value.close()
      eventSource.value = null
      connected.value = false
    }
  }

  onMounted(() => {
    connect()
  })

  onUnmounted(() => {
    disconnect()
  })

  return {
    connected,
    error,
    disconnect,
    reconnect: connect
  }
}
