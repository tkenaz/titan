import { createApi } from '@reduxjs/toolkit/query/react'
import { createBaseQuery, API_ENDPOINTS } from './baseApi'

// Types
export interface Memory {
  id: string
  content: string
  summary: string
  priority: number
  metadata: Record<string, any>
  created_at: string
  updated_at: string
  embedding?: number[]
}

export interface MemoryStats {
  total_memories: number
  duplicate_memories: number
  average_priority: number
  memory_by_priority: Record<string, number>
}

export interface CostStats {
  total_cost: number
  total_tokens: number
  cost_by_model: Record<string, number>
  tokens_by_model: Record<string, number>
  daily_costs: Array<{
    date: string
    cost: number
    tokens: number
  }>
}

export interface SearchResult {
  memories: Array<Memory & { score: number }>
  total: number
}

// API slice
export const memoryApi = createApi({
  reducerPath: 'memoryApi',
  baseQuery: createBaseQuery(API_ENDPOINTS.memory),
  tagTypes: ['Memory', 'Stats', 'Cost'],
  endpoints: (builder) => ({
    // Get memory stats
    getMemoryStats: builder.query<MemoryStats, void>({
      query: () => '/memory/stats',
      providesTags: ['Stats'],
    }),

    // Search memories
    searchMemories: builder.query<SearchResult, { query: string; limit?: number }>({
      query: ({ query, limit = 10 }) => ({
        url: '/memory/search',
        params: { q: query, limit },
      }),
      providesTags: ['Memory'],
    }),

    // Create memory
    createMemory: builder.mutation<Memory, Omit<Memory, 'id' | 'created_at' | 'updated_at'>>({
      query: (memory) => ({
        url: '/memory',
        method: 'POST',
        body: memory,
      }),
      invalidatesTags: ['Memory', 'Stats'],
    }),

    // Update memory
    updateMemory: builder.mutation<Memory, { id: string; updates: Partial<Memory> }>({
      query: ({ id, updates }) => ({
        url: `/memory/${id}`,
        method: 'PUT',
        body: updates,
      }),
      invalidatesTags: ['Memory', 'Stats'],
    }),

    // Delete memory
    deleteMemory: builder.mutation<void, string>({
      query: (id) => ({
        url: `/memory/${id}`,
        method: 'DELETE',
      }),
      invalidatesTags: ['Memory', 'Stats'],
    }),

    // Get cost stats
    getCostStats: builder.query<CostStats, { days?: number }>({
      query: ({ days = 7 }) => ({
        url: '/memory/cost',
        params: { days },
      }),
      providesTags: ['Cost'],
    }),

    // Create insight (high priority memory)
    createInsight: builder.mutation<Memory, { content: string; metadata?: Record<string, any> }>({
      query: (insight) => ({
        url: '/memory/insight',
        method: 'POST',
        body: insight,
      }),
      invalidatesTags: ['Memory', 'Stats'],
    }),
  }),
})

export const {
  useGetMemoryStatsQuery,
  useSearchMemoriesQuery,
  useCreateMemoryMutation,
  useUpdateMemoryMutation,
  useDeleteMemoryMutation,
  useGetCostStatsQuery,
  useCreateInsightMutation,
} = memoryApi
