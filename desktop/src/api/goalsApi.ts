import { createApi } from '@reduxjs/toolkit/query/react'
import { createBaseQuery, API_ENDPOINTS } from './baseApi'

// Types
export interface Goal {
  goal_id: string
  name: string
  description?: string
  goal_type: 'system' | 'user' | 'experiment'
  schedule: string // cron expression
  priority: 'low' | 'medium' | 'high' | 'critical'
  enabled: boolean
  template: string
  params: Record<string, any>
  retry_count: number
  timeout_seconds: number
  last_run?: string
  next_run?: string
  status?: 'scheduled' | 'running' | 'succeeded' | 'failed'
  last_error?: string
}

export interface GoalStats {
  total_goals: number
  enabled_goals: number
  scheduled_goals: number
  failed_goals: number
  goals_by_type: Record<string, number>
  goals_by_priority: Record<string, number>
}

export interface GoalExecution {
  execution_id: string
  goal_id: string
  started_at: string
  completed_at?: string
  status: 'running' | 'succeeded' | 'failed'
  duration_seconds?: number
  error?: string
  result?: any
}

// API slice
export const goalsApi = createApi({
  reducerPath: 'goalsApi',
  baseQuery: createBaseQuery(API_ENDPOINTS.goals),
  tagTypes: ['Goal', 'GoalStats', 'GoalExecution'],
  endpoints: (builder) => ({
    // Get all goals
    getGoals: builder.query<Goal[], void>({
      query: () => '/goals',
      providesTags: ['Goal'],
    }),

    // Get goal stats
    getGoalStats: builder.query<GoalStats, void>({
      query: () => '/goals/stats',
      providesTags: ['GoalStats'],
    }),

    // Get goal details
    getGoal: builder.query<Goal, string>({
      query: (id) => `/goals/${id}`,
      providesTags: (result, error, id) => [{ type: 'Goal', id }],
    }),

    // Create goal
    createGoal: builder.mutation<Goal, Omit<Goal, 'goal_id' | 'last_run' | 'next_run' | 'status'>>({
      query: (goal) => ({
        url: '/goals',
        method: 'POST',
        body: goal,
      }),
      invalidatesTags: ['Goal', 'GoalStats'],
    }),

    // Update goal
    updateGoal: builder.mutation<Goal, { id: string; updates: Partial<Goal> }>({
      query: ({ id, updates }) => ({
        url: `/goals/${id}`,
        method: 'PUT',
        body: updates,
      }),
      invalidatesTags: (result, error, { id }) => [
        { type: 'Goal', id },
        'Goal',
        'GoalStats',
      ],
    }),

    // Delete goal
    deleteGoal: builder.mutation<void, string>({
      query: (id) => ({
        url: `/goals/${id}`,
        method: 'DELETE',
      }),
      invalidatesTags: ['Goal', 'GoalStats'],
    }),

    // Enable/disable goal
    toggleGoal: builder.mutation<Goal, { id: string; enabled: boolean }>({
      query: ({ id, enabled }) => ({
        url: `/goals/${id}/${enabled ? 'enable' : 'disable'}`,
        method: 'POST',
      }),
      invalidatesTags: (result, error, { id }) => [
        { type: 'Goal', id },
        'Goal',
        'GoalStats',
      ],
    }),

    // Execute goal now
    executeGoal: builder.mutation<GoalExecution, string>({
      query: (id) => ({
        url: `/goals/${id}/execute`,
        method: 'POST',
      }),
      invalidatesTags: (result, error, id) => [
        { type: 'Goal', id },
        'GoalExecution',
      ],
    }),

    // Get goal executions
    getGoalExecutions: builder.query<GoalExecution[], { goalId?: string; limit?: number }>({
      query: ({ goalId, limit = 20 }) => ({
        url: '/goals/executions',
        params: { goal_id: goalId, limit },
      }),
      providesTags: ['GoalExecution'],
    }),

    // Pause scheduler
    pauseScheduler: builder.mutation<void, void>({
      query: () => ({
        url: '/goals/scheduler/pause',
        method: 'POST',
      }),
      invalidatesTags: ['Goal', 'GoalStats'],
    }),

    // Resume scheduler
    resumeScheduler: builder.mutation<void, void>({
      query: () => ({
        url: '/goals/scheduler/resume',
        method: 'POST',
      }),
      invalidatesTags: ['Goal', 'GoalStats'],
    }),
  }),
})

export const {
  useGetGoalsQuery,
  useGetGoalStatsQuery,
  useGetGoalQuery,
  useCreateGoalMutation,
  useUpdateGoalMutation,
  useDeleteGoalMutation,
  useToggleGoalMutation,
  useExecuteGoalMutation,
  useGetGoalExecutionsQuery,
  usePauseSchedulerMutation,
  useResumeSchedulerMutation,
} = goalsApi
