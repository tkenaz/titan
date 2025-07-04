import { Middleware } from '@reduxjs/toolkit'
import { RootState } from '../store'
import { addEvent, setConnectionStatus } from '../store/slices/eventsSlice'
import { API_ENDPOINTS } from '../api/baseApi'

export interface WebSocketEvent {
  type: string
  timestamp: string
  [key: string]: any
}

let ws: WebSocket | null = null
let reconnectTimeout: NodeJS.Timeout | null = null
let reconnectAttempts = 0
const MAX_RECONNECT_ATTEMPTS = 5
const RECONNECT_DELAY = 3000

export const websocketMiddleware: Middleware<{}, RootState> = (store) => (next) => (action) => {
  // Handle websocket actions
  if (action.type === 'websocket/connect') {
    connectWebSocket(store)
  } else if (action.type === 'websocket/disconnect') {
    disconnectWebSocket()
  }

  return next(action)
}

function connectWebSocket(store: any) {
  if (ws?.readyState === WebSocket.OPEN) {
    return
  }

  try {
    ws = new WebSocket(API_ENDPOINTS.websocket)

    ws.onopen = () => {
      console.log('WebSocket connected')
      store.dispatch(setConnectionStatus('connected'))
      reconnectAttempts = 0
    }

    ws.onmessage = (event) => {
      try {
        const data: WebSocketEvent = JSON.parse(event.data)
        
        // Add timestamp if not present
        if (!data.timestamp) {
          data.timestamp = new Date().toISOString()
        }

        // Dispatch event to store
        store.dispatch(addEvent(data))

        // Handle specific event types
        handleSpecificEvents(data, store)
      } catch (error) {
        console.error('Failed to parse WebSocket message:', error)
      }
    }

    ws.onerror = (error) => {
      console.error('WebSocket error:', error)
      store.dispatch(setConnectionStatus('error'))
    }

    ws.onclose = () => {
      console.log('WebSocket disconnected')
      store.dispatch(setConnectionStatus('disconnected'))
      ws = null

      // Attempt to reconnect
      if (reconnectAttempts < MAX_RECONNECT_ATTEMPTS) {
        reconnectAttempts++
        reconnectTimeout = setTimeout(() => {
          console.log(`Attempting to reconnect (${reconnectAttempts}/${MAX_RECONNECT_ATTEMPTS})...`)
          connectWebSocket(store)
        }, RECONNECT_DELAY)
      }
    }
  } catch (error) {
    console.error('Failed to create WebSocket:', error)
    store.dispatch(setConnectionStatus('error'))
  }
}

function disconnectWebSocket() {
  if (reconnectTimeout) {
    clearTimeout(reconnectTimeout)
    reconnectTimeout = null
  }
  
  if (ws) {
    ws.close()
    ws = null
  }
  
  reconnectAttempts = MAX_RECONNECT_ATTEMPTS // Prevent auto-reconnect
}

function handleSpecificEvents(event: WebSocketEvent, store: any) {
  switch (event.type) {
    case 'model.request':
      // Update cost tracking
      if (event.cost) {
        // You might want to dispatch an action to update cost in real-time
      }
      break
      
    case 'plugin.error':
      // Could show a notification
      console.error(`Plugin error: ${event.plugin} - ${event.error}`)
      break
      
    case 'goal.finished':
      // Invalidate goal queries to refresh data
      store.dispatch(
        store.api.util.invalidateTags([
          { type: 'Goal', id: event.goal_id },
          'GoalStats',
          'GoalExecution'
        ])
      )
      break
      
    case 'memory.created':
    case 'memory.updated':
    case 'memory.deleted':
      // Invalidate memory queries
      store.dispatch(
        store.api.util.invalidateTags(['Memory', 'Stats'])
      )
      break
  }
}

// Action creators
export const connectWebSocketAction = () => ({ type: 'websocket/connect' })
export const disconnectWebSocketAction = () => ({ type: 'websocket/disconnect' })
