import { fetchBaseQuery } from '@reduxjs/toolkit/query'
import type { RootState } from '../store'

// Base query with auth
export const createBaseQuery = (baseUrl: string) => fetchBaseQuery({
  baseUrl,
  prepareHeaders: (headers, { getState }) => {
    const token = (getState() as RootState).auth.token
    if (token) {
      headers.set('Authorization', `Bearer ${token}`)
    }
    headers.set('Content-Type', 'application/json')
    return headers
  },
})

// API endpoints configuration
export const API_ENDPOINTS = {
  memory: 'http://localhost:8001',
  plugins: 'http://localhost:8003',
  goals: 'http://localhost:8005',
  gateway: 'http://localhost:8081',
  websocket: 'ws://localhost:8088/events'
}
