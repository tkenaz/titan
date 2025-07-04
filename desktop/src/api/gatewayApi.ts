import { createApi } from '@reduxjs/toolkit/query/react'
import { createBaseQuery, API_ENDPOINTS } from './baseApi'

// Types
export interface Model {
  id: string
  name: string
  provider: 'openai' | 'anthropic' | 'google'
  max_tokens: number
  input_price_per_1k: number
  output_price_per_1k: number
  cache_price_per_1k?: number
  average_latency_ms: number
  capabilities: string[]
  recommended_for: string[]
}

export interface ModelRequest {
  model: string
  messages: Array<{
    role: 'system' | 'user' | 'assistant'
    content: string
  }>
  max_tokens?: number
  temperature?: number
  stream?: boolean
}

export interface ModelResponse {
  id: string
  model: string
  usage: {
    prompt_tokens: number
    completion_tokens: number
    total_tokens: number
    cost_usd: number
  }
  choices: Array<{
    message: {
      role: string
      content: string
    }
    finish_reason: string
  }>
  latency_ms: number
}

export interface ModelPreferences {
  default_model: string
  task_models: {
    self_reflection: string
    vitals_check: string
    experiment: string
    general: string
  }
}

// HMAC helper using Web Crypto API
const generateHmac = async (data: string, secret: string): Promise<string> => {
  const encoder = new TextEncoder()
  const keyData = encoder.encode(secret)
  const algorithm = { name: 'HMAC', hash: 'SHA-256' }
  
  const key = await crypto.subtle.importKey(
    'raw',
    keyData,
    algorithm,
    false,
    ['sign']
  )
  
  const signature = await crypto.subtle.sign(
    algorithm,
    key,
    encoder.encode(data)
  )
  
  return Array.from(new Uint8Array(signature))
    .map(b => b.toString(16).padStart(2, '0'))
    .join('')
}

// API slice
export const gatewayApi = createApi({
  reducerPath: 'gatewayApi',
  baseQuery: createBaseQuery(API_ENDPOINTS.gateway),
  tagTypes: ['Model', 'ModelPreferences'],
  endpoints: (builder) => ({
    // Get available models
    getModels: builder.query<Model[], void>({
      query: () => '/models',
      providesTags: ['Model'],
    }),

    // Get model details
    getModel: builder.query<Model, string>({
      query: (id) => `/models/${id}`,
      providesTags: (result, error, id) => [{ type: 'Model', id }],
    }),

    // Get model preferences
    getModelPreferences: builder.query<ModelPreferences, void>({
      query: () => '/models/preferences',
      providesTags: ['ModelPreferences'],
    }),

    // Update model preferences
    updateModelPreferences: builder.mutation<ModelPreferences, Partial<ModelPreferences>>({
      query: (preferences) => ({
        url: '/models/preferences',
        method: 'PUT',
        body: preferences,
      }),
      invalidatesTags: ['ModelPreferences'],
    }),

    // Send model request
    sendModelRequest: builder.mutation<ModelResponse, ModelRequest>({
      query: async (request) => {
        const hmacSecret = import.meta.env.VITE_HMAC_SECRET || 'titan-hmac-secret-change-me-in-production'
        const signature = await generateHmac(JSON.stringify(request), hmacSecret)
        
        return {
          url: '/chat/completions',
          method: 'POST',
          body: request,
          headers: {
            'X-HMAC-Signature': signature,
          },
        }
      },
    }),

    // Stream model response (returns EventSource URL)
    streamModelRequest: builder.mutation<{ stream_url: string; stream_id: string }, ModelRequest>({
      query: async (request) => {
        const hmacSecret = import.meta.env.VITE_HMAC_SECRET || 'titan-hmac-secret-change-me-in-production'
        const requestWithStream = { ...request, stream: true }
        const signature = await generateHmac(JSON.stringify(requestWithStream), hmacSecret)
        
        return {
          url: '/chat/completions/stream',
          method: 'POST',
          body: requestWithStream,
          headers: {
            'X-HMAC-Signature': signature,
          },
        }
      },
    }),

    // Get model usage stats
    getModelUsageStats: builder.query<{
      total_requests: number
      total_tokens: number
      total_cost_usd: number
      by_model: Record<string, {
        requests: number
        tokens: number
        cost_usd: number
        average_latency_ms: number
      }>
    }, { days?: number }>({
      query: ({ days = 7 }) => ({
        url: '/models/usage',
        params: { days },
      }),
    }),
  }),
})

export const {
  useGetModelsQuery,
  useGetModelQuery,
  useGetModelPreferencesQuery,
  useUpdateModelPreferencesMutation,
  useSendModelRequestMutation,
  useStreamModelRequestMutation,
  useGetModelUsageStatsQuery,
} = gatewayApi
