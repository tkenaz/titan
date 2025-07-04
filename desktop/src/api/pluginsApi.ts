import { createApi } from '@reduxjs/toolkit/query/react'
import { createBaseQuery, API_ENDPOINTS } from './baseApi'

// Types
export interface Plugin {
  name: string
  version: string
  state: 'active' | 'inactive' | 'failed' | 'loading'
  description?: string
  author?: string
  last_run?: string
  error_count: number
  last_error?: string
  capabilities: string[]
  config?: Record<string, any>
}

export interface PluginStats {
  total_plugins: number
  active_plugins: number
  failed_plugins: number
  total_executions: number
  total_errors: number
}

export interface PluginLog {
  timestamp: string
  level: 'INFO' | 'WARNING' | 'ERROR' | 'DEBUG'
  message: string
  plugin_name: string
}

// API slice
export const pluginsApi = createApi({
  reducerPath: 'pluginsApi',
  baseQuery: createBaseQuery(API_ENDPOINTS.plugins),
  tagTypes: ['Plugin', 'PluginStats', 'PluginLogs'],
  endpoints: (builder) => ({
    // Get all plugins
    getPlugins: builder.query<Plugin[], void>({
      query: () => '/plugins',
      providesTags: ['Plugin'],
    }),

    // Get plugin stats
    getPluginStats: builder.query<PluginStats, void>({
      query: () => '/plugins/stats',
      providesTags: ['PluginStats'],
    }),

    // Get plugin details
    getPlugin: builder.query<Plugin, string>({
      query: (name) => `/plugins/${name}`,
      providesTags: (result, error, name) => [{ type: 'Plugin', id: name }],
    }),

    // Enable/disable plugin
    togglePlugin: builder.mutation<Plugin, { name: string; enabled: boolean }>({
      query: ({ name, enabled }) => ({
        url: `/plugins/${name}/${enabled ? 'enable' : 'disable'}`,
        method: 'POST',
      }),
      invalidatesTags: (result, error, { name }) => [
        { type: 'Plugin', id: name },
        'Plugin',
        'PluginStats',
      ],
    }),

    // Reload plugin
    reloadPlugin: builder.mutation<Plugin, string>({
      query: (name) => ({
        url: `/plugins/${name}/reload`,
        method: 'POST',
      }),
      invalidatesTags: (result, error, name) => [
        { type: 'Plugin', id: name },
        'Plugin',
      ],
    }),

    // Execute plugin
    executePlugin: builder.mutation<any, { name: string; params?: Record<string, any> }>({
      query: ({ name, params }) => ({
        url: `/plugins/${name}/execute`,
        method: 'POST',
        body: params || {},
      }),
      invalidatesTags: (result, error, { name }) => [
        { type: 'Plugin', id: name },
        'PluginStats',
      ],
    }),

    // Get plugin logs
    getPluginLogs: builder.query<string, { name: string; tail?: number }>({
      query: ({ name, tail = 2000 }) => ({
        url: `/plugins/logs`,
        params: { plugin: name, tail },
      }),
      providesTags: ['PluginLogs'],
    }),

    // Hot reload all plugins
    hotReload: builder.mutation<void, void>({
      query: () => ({
        url: '/plugins/hot-reload',
        method: 'POST',
      }),
      invalidatesTags: ['Plugin', 'PluginStats'],
    }),
  }),
})

export const {
  useGetPluginsQuery,
  useGetPluginStatsQuery,
  useGetPluginQuery,
  useTogglePluginMutation,
  useReloadPluginMutation,
  useExecutePluginMutation,
  useGetPluginLogsQuery,
  useHotReloadMutation,
} = pluginsApi
