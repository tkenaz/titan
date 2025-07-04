import { createSlice, PayloadAction } from '@reduxjs/toolkit'

export interface TitanEvent {
  type: string
  timestamp: string
  [key: string]: any
}

interface EventsState {
  events: TitanEvent[]
  connectionStatus: 'disconnected' | 'connecting' | 'connected' | 'error'
  stats: {
    totalRequests: number
    totalCost: number
    activePlugins: number
    scheduledGoals: number
  }
}

const initialState: EventsState = {
  events: [],
  connectionStatus: 'disconnected',
  stats: {
    totalRequests: 0,
    totalCost: 0,
    activePlugins: 0,
    scheduledGoals: 0,
  },
}

const eventsSlice = createSlice({
  name: 'events',
  initialState,
  reducers: {
    setConnectionStatus: (state, action: PayloadAction<EventsState['connectionStatus']>) => {
      state.connectionStatus = action.payload
    },
    addEvent: (state, action: PayloadAction<TitanEvent>) => {
      // Add to beginning and keep only last 100 events
      state.events = [action.payload, ...state.events].slice(0, 100)
      
      // Update stats based on event type
      const event = action.payload
      switch (event.type) {
        case 'model.request':
          state.stats.totalRequests++
          state.stats.totalCost += event.cost || 0
          break
        case 'plugin.started':
          state.stats.activePlugins++
          break
        case 'plugin.stopped':
          state.stats.activePlugins = Math.max(0, state.stats.activePlugins - 1)
          break
        case 'goal.scheduled':
          state.stats.scheduledGoals++
          break
        case 'goal.finished':
          state.stats.scheduledGoals = Math.max(0, state.stats.scheduledGoals - 1)
          break
      }
    },
    clearEvents: (state) => {
      state.events = []
    },
    updateStats: (state, action: PayloadAction<Partial<EventsState['stats']>>) => {
      state.stats = { ...state.stats, ...action.payload }
    },
  },
})

export const { setConnectionStatus, addEvent, clearEvents, updateStats } = eventsSlice.actions
export default eventsSlice.reducer
