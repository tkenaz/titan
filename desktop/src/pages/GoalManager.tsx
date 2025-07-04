import React, { useState } from 'react'
import { 
  Play, 
  Pause, 
  Clock, 
  Calendar,
  AlertCircle,
  CheckCircle,
  Target,
  Plus
} from 'lucide-react'
import { DataTable } from '../components/common/DataTable'
import { 
  useGetGoalsQuery,
  useToggleGoalMutation,
  useExecuteGoalMutation,
  useGetGoalExecutionsQuery,
  Goal
} from '../api/goalsApi'
import { format } from 'date-fns'
import cronstrue from 'cronstrue'

// Helper to parse cron expression
const getCronDescription = (schedule: string) => {
  try {
    return cronstrue.toString(schedule)
  } catch {
    return schedule
  }
}

interface GoalDetailModalProps {
  goal: Goal
  onClose: () => void
}

const GoalDetailModal: React.FC<GoalDetailModalProps> = ({ goal, onClose }) => {
  const { data: executions, isLoading } = useGetGoalExecutionsQuery({ 
    goalId: goal.goal_id, 
    limit: 10 
  })
  const [executeGoal] = useExecuteGoalMutation()

  const handleExecute = async () => {
    try {
      await executeGoal(goal.goal_id).unwrap()
    } catch (error) {
      console.error('Failed to execute goal:', error)
    }
  }

  return (
    <div className="fixed inset-0 z-50 overflow-hidden">
      <div className="absolute inset-0 bg-black bg-opacity-50" onClick={onClose} />
      <div className="absolute inset-0 flex items-center justify-center p-4">
        <div className="bg-gray-800 rounded-lg shadow-xl max-w-4xl w-full max-h-[80vh] flex flex-col">
          <div className="flex items-center justify-between border-b border-gray-700 px-6 py-4">
            <h2 className="text-lg font-semibold">{goal.name}</h2>
            <button
              onClick={onClose}
              className="text-gray-400 hover:text-white transition-colors"
            >
              ✕
            </button>
          </div>

          <div className="flex-1 overflow-y-auto p-6">
            <div className="space-y-6">
              {/* Goal Details */}
              <div className="grid grid-cols-2 gap-6">
                <div>
                  <h3 className="text-sm font-medium text-gray-400 mb-2">Description</h3>
                  <p className="text-gray-300">{goal.description || 'No description'}</p>
                </div>
                <div>
                  <h3 className="text-sm font-medium text-gray-400 mb-2">Schedule</h3>
                  <p className="text-gray-300 font-mono text-sm">{goal.schedule}</p>
                  <p className="text-xs text-gray-500 mt-1">{getCronDescription(goal.schedule)}</p>
                </div>
                <div>
                  <h3 className="text-sm font-medium text-gray-400 mb-2">Type</h3>
                  <span className="inline-flex items-center px-2.5 py-0.5 rounded text-xs font-medium bg-gray-700 text-gray-300">
                    {goal.goal_type}
                  </span>
                </div>
                <div>
                  <h3 className="text-sm font-medium text-gray-400 mb-2">Priority</h3>
                  <span className={`inline-flex items-center px-2.5 py-0.5 rounded text-xs font-medium ${
                    goal.priority === 'critical' ? 'bg-red-900 text-red-300' :
                    goal.priority === 'high' ? 'bg-orange-900 text-orange-300' :
                    goal.priority === 'medium' ? 'bg-yellow-900 text-yellow-300' :
                    'bg-gray-700 text-gray-300'
                  }`}>
                    {goal.priority}
                  </span>
                </div>
                <div>
                  <h3 className="text-sm font-medium text-gray-400 mb-2">Next Run</h3>
                  <p className="text-gray-300">
                    {goal.next_run ? format(new Date(goal.next_run), 'PPp') : 'Not scheduled'}
                  </p>
                </div>
                <div>
                  <h3 className="text-sm font-medium text-gray-400 mb-2">Last Run</h3>
                  <p className="text-gray-300">
                    {goal.last_run ? format(new Date(goal.last_run), 'PPp') : 'Never'}
                  </p>
                </div>
              </div>

              {/* Template */}
              <div>
                <h3 className="text-sm font-medium text-gray-400 mb-2">Template</h3>
                <pre className="text-xs bg-gray-900 p-3 rounded overflow-x-auto">
                  {goal.template}
                </pre>
              </div>

              {/* Parameters */}
              {Object.keys(goal.params).length > 0 && (
                <div>
                  <h3 className="text-sm font-medium text-gray-400 mb-2">Parameters</h3>
                  <pre className="text-xs bg-gray-900 p-3 rounded overflow-x-auto">
                    {JSON.stringify(goal.params, null, 2)}
                  </pre>
                </div>
              )}

              {/* Recent Executions */}
              <div>
                <h3 className="text-sm font-medium text-gray-400 mb-3">Recent Executions</h3>
                {isLoading ? (
                  <div className="flex justify-center py-4">
                    <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-white"></div>
                  </div>
                ) : executions && executions.length > 0 ? (
                  <div className="space-y-2">
                    {executions.map((exec) => (
                      <div key={exec.execution_id} className="flex items-center justify-between bg-gray-900 p-3 rounded">
                        <div className="flex items-center gap-3">
                          {exec.status === 'succeeded' ? (
                            <CheckCircle className="h-4 w-4 text-green-500" />
                          ) : exec.status === 'failed' ? (
                            <AlertCircle className="h-4 w-4 text-red-500" />
                          ) : (
                            <Clock className="h-4 w-4 text-yellow-500 animate-spin" />
                          )}
                          <span className="text-sm">
                            {format(new Date(exec.started_at), 'MMM d, HH:mm')}
                          </span>
                        </div>
                        <div className="text-right">
                          {exec.duration_seconds && (
                            <span className="text-xs text-gray-400">
                              {exec.duration_seconds}s
                            </span>
                          )}
                          {exec.error && (
                            <p className="text-xs text-red-400 mt-1 max-w-xs truncate">
                              {exec.error}
                            </p>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-sm text-gray-500">No executions yet</p>
                )}
              </div>
            </div>
          </div>

          <div className="border-t border-gray-700 px-6 py-4 flex justify-end gap-3">
            <button
              onClick={handleExecute}
              disabled={!goal.enabled}
              className="px-4 py-2 text-sm bg-blue-600 hover:bg-blue-700 disabled:bg-gray-700 text-white rounded-lg transition-colors flex items-center gap-2"
            >
              <Play className="h-4 w-4" />
              Execute Now
            </button>
            <button
              onClick={onClose}
              className="px-4 py-2 text-sm bg-gray-700 hover:bg-gray-600 text-white rounded-lg transition-colors"
            >
              Close
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

export const GoalManager: React.FC = () => {
  const { data: goals, isLoading } = useGetGoalsQuery()
  const [toggleGoal] = useToggleGoalMutation()
  const [executeGoal] = useExecuteGoalMutation()
  const [selectedGoal, setSelectedGoal] = useState<Goal | null>(null)

  const handleToggle = async (goal: Goal) => {
    try {
      await toggleGoal({ id: goal.goal_id, enabled: !goal.enabled }).unwrap()
    } catch (error) {
      console.error('Failed to toggle goal:', error)
    }
  }

  const handleExecute = async (goal: Goal) => {
    try {
      await executeGoal(goal.goal_id).unwrap()
    } catch (error) {
      console.error('Failed to execute goal:', error)
    }
  }

  const getStatusIcon = (goal: Goal) => {
    if (!goal.enabled) return <Pause className="h-4 w-4 text-gray-500" />
    if (goal.status === 'running') return <Clock className="h-4 w-4 text-yellow-500 animate-spin" />
    if (goal.status === 'failed') return <AlertCircle className="h-4 w-4 text-red-500" />
    return <CheckCircle className="h-4 w-4 text-green-500" />
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Goal Manager</h1>
          <p className="text-gray-400 mt-1">Schedule and manage autonomous goals</p>
        </div>
        <button className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors flex items-center gap-2">
          <Plus className="h-5 w-5" />
          New Goal
        </button>
      </div>

      <DataTable
        data={goals || []}
        loading={isLoading}
        onRowClick={setSelectedGoal}
        columns={[
          {
            key: 'name',
            label: 'Goal',
            render: (goal) => (
              <div>
                <p className="font-medium text-white">{goal.name}</p>
                <p className="text-xs text-gray-400 mt-1">{goal.description || 'No description'}</p>
              </div>
            )
          },
          {
            key: 'status',
            label: 'Status',
            render: (goal) => (
              <div className="flex items-center gap-2">
                {getStatusIcon(goal)}
                <span className={`text-sm ${
                  !goal.enabled ? 'text-gray-500' :
                  goal.status === 'running' ? 'text-yellow-500' :
                  goal.status === 'failed' ? 'text-red-500' :
                  'text-green-500'
                }`}>
                  {!goal.enabled ? 'Disabled' : (goal.status || 'Scheduled')}
                </span>
              </div>
            )
          },
          {
            key: 'schedule',
            label: 'Schedule',
            render: (goal) => (
              <div>
                <p className="text-sm font-mono">{goal.schedule}</p>
                <p className="text-xs text-gray-500 mt-1">{getCronDescription(goal.schedule)}</p>
              </div>
            )
          },
          {
            key: 'priority',
            label: 'Priority',
            render: (goal) => (
              <span className={`inline-flex items-center px-2.5 py-0.5 rounded text-xs font-medium ${
                goal.priority === 'critical' ? 'bg-red-900 text-red-300' :
                goal.priority === 'high' ? 'bg-orange-900 text-orange-300' :
                goal.priority === 'medium' ? 'bg-yellow-900 text-yellow-300' :
                'bg-gray-700 text-gray-300'
              }`}>
                {goal.priority}
              </span>
            )
          },
          {
            key: 'next_run',
            label: 'Next Run',
            render: (goal) => (
              <span className="text-sm text-gray-400">
                {goal.enabled && goal.next_run 
                  ? format(new Date(goal.next_run), 'MMM d, HH:mm')
                  : '-'
                }
              </span>
            )
          },
          {
            key: 'actions',
            label: 'Actions',
            render: (goal) => (
              <div className="flex items-center gap-2">
                <button
                  onClick={(e) => {
                    e.stopPropagation()
                    handleExecute(goal)
                  }}
                  disabled={!goal.enabled}
                  className="p-2 text-gray-400 hover:text-white disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                  title="Execute Now"
                >
                  <Play className="h-4 w-4" />
                </button>
                <button
                  onClick={(e) => {
                    e.stopPropagation()
                    handleToggle(goal)
                  }}
                  className={`p-2 transition-colors ${
                    goal.enabled 
                      ? 'text-green-500 hover:text-green-400' 
                      : 'text-gray-400 hover:text-white'
                  }`}
                  title={goal.enabled ? 'Pause' : 'Resume'}
                >
                  {goal.enabled ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4" />}
                </button>
              </div>
            )
          }
        ]}
      />

      {/* Goal Detail Modal */}
      {selectedGoal && (
        <GoalDetailModal
          goal={selectedGoal}
          onClose={() => setSelectedGoal(null)}
        />
      )}
    </div>
  )
}
