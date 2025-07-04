import { configureStore } from '@reduxjs/toolkit'
import { setupListeners } from '@reduxjs/toolkit/query'
import authReducer from './slices/authSlice'
import uiReducer from './slices/uiSlice'
import eventsReducer from './slices/eventsSlice'
import { memoryApi } from '../api/memoryApi'
import { pluginsApi } from '../api/pluginsApi'
import { goalsApi } from '../api/goalsApi'
import { gatewayApi } from '../api/gatewayApi'
import { websocketMiddleware } from '../middleware/websocketMiddleware'

export const store = configureStore({
  reducer: {
    auth: authReducer,
    ui: uiReducer,
    events: eventsReducer,
    [memoryApi.reducerPath]: memoryApi.reducer,
    [pluginsApi.reducerPath]: pluginsApi.reducer,
    [goalsApi.reducerPath]: goalsApi.reducer,
    [gatewayApi.reducerPath]: gatewayApi.reducer,
  },
  middleware: (getDefaultMiddleware) =>
    getDefaultMiddleware({
      serializableCheck: {
        // Ignore these action types
        ignoredActions: ['events/addEvent', 'websocket/connect', 'websocket/disconnect'],
      },
    }).concat(
      websocketMiddleware,
      memoryApi.middleware,
      pluginsApi.middleware,
      goalsApi.middleware,
      gatewayApi.middleware
    ),
})

// Enable refetch on focus/reconnect
setupListeners(store.dispatch)

export type RootState = ReturnType<typeof store.getState>
export type AppDispatch = typeof store.dispatch
