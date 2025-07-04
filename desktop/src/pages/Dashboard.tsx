import React from 'react'
import { 
  Brain, 
  Database, 
  Puzzle, 
  Target, 
  DollarSign
} from 'lucide-react'
import { StatsCard } from '../components/common/StatsCard'
import { EventFeed } from '../components/common/EventFeed'
import { DataTable } from '../components/common/DataTable'
import { useGetMemoryStatsQuery, useGetCostStatsQuery } from '../api/memoryApi'
import { useGetPluginStatsQuery } from '../api/pluginsApi'
import { useGetGoalStatsQuery } from '../api/goalsApi'
import { useGetModelUsageStatsQuery } from '../api/gatewayApi'

export const Dashboard: React.FC = () => {
  // Fetch all stats
  const { data: memoryStats } = useGetMemoryStatsQuery()
  const { data: pluginStats } = useGetPluginStatsQuery()
  const { data: goalStats } = useGetGoalStatsQuery()
  const { data: costStats } = useGetCostStatsQuery({ days: 1 })
  const { data: modelUsage } = useGetModelUsageStatsQuery({ days: 7 })

  // Calculate trends (mock data for now - in real app, compare with yesterday)
  const costTrend = costStats?.daily_costs?.length > 1 
    ? ((costStats.daily_costs[0].cost - costStats.daily_costs[1].cost) / costStats.daily_costs[1].cost) * 100
    : 0

  // Format model usage data for table
  const modelData = Object.entries(modelUsage?.by_model || {}).map(([model, stats]) => ({
    model,
    requests: stats.requests,
    tokens: stats.tokens,
    cost: stats.cost_usd,
    avgLatency: stats.average_latency_ms
  }))

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Dashboard</h1>
        <p className="text-gray-400 mt-1">System overview and real-time monitoring</p>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <StatsCard
          title="Memories Stored"
          value={memoryStats?.total_memories || 0}
          subtitle={`${memoryStats?.duplicate_memories || 0} duplicates`}
          icon={Database}
          color="blue"
          trend={{
            value: 12,
            isPositive: true
          }}
        />

        <StatsCard
          title="Active Plugins"
          value={pluginStats?.active_plugins || 0}
          subtitle={`${pluginStats?.failed_plugins || 0} failed`}
          icon={Puzzle}
          color="purple"
          trend={{
            value: pluginStats?.failed_plugins ? -5 : 0,
            isPositive: false
          }}
        />

        <StatsCard
          title="Scheduled Goals"
          value={goalStats?.scheduled_goals || 0}
          subtitle={`${goalStats?.enabled_goals || 0} enabled`}
          icon={Target}
          color="green"
        />

        <StatsCard
          title="Daily Cost"
          value={`$${costStats?.daily_costs?.[0]?.cost?.toFixed(2) || '0.00'}`}
          subtitle={`${costStats?.daily_costs?.[0]?.tokens || 0} tokens`}
          icon={DollarSign}
          color={costTrend > 50 ? 'red' : costTrend > 20 ? 'yellow' : 'green'}
          trend={costTrend ? {
            value: Math.abs(costTrend),
            isPositive: costTrend < 0
          } : undefined}
        />
      </div>

      {/* Main Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Model Usage Table */}
        <div className="lg:col-span-2">
          <div className="bg-gray-800 rounded-lg border border-gray-700 p-6">
            <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
              <Brain className="w-5 h-5" />
              Model Usage (7 days)
            </h2>
            <DataTable
              data={modelData}
              columns={[
                { key: 'model', label: 'Model' },
                { 
                  key: 'requests', 
                  label: 'Requests',
                  render: (item) => item.requests.toLocaleString()
                },
                { 
                  key: 'tokens', 
                  label: 'Tokens',
                  render: (item) => item.tokens.toLocaleString()
                },
                { 
                  key: 'cost', 
                  label: 'Cost',
                  render: (item) => `$${item.cost.toFixed(2)}`
                },
                { 
                  key: 'avgLatency', 
                  label: 'Avg Latency',
                  render: (item) => `${item.avgLatency}ms`
                },
              ]}
            />
          </div>
        </div>

        {/* Event Feed */}
        <div className="lg:col-span-1">
          <EventFeed maxHeight="500px" />
        </div>
      </div>

      {/* Additional Stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="bg-gray-800 rounded-lg border border-gray-700 p-6">
          <h3 className="text-sm font-medium text-gray-400 mb-2">Memory by Priority</h3>
          <div className="space-y-2">
            {Object.entries(memoryStats?.memory_by_priority || {}).map(([priority, count]) => (
              <div key={priority} className="flex justify-between items-center">
                <span className="text-sm capitalize">{priority}</span>
                <span className="text-sm font-medium">{count}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="bg-gray-800 rounded-lg border border-gray-700 p-6">
          <h3 className="text-sm font-medium text-gray-400 mb-2">Goals by Type</h3>
          <div className="space-y-2">
            {Object.entries(goalStats?.goals_by_type || {}).map(([type, count]) => (
              <div key={type} className="flex justify-between items-center">
                <span className="text-sm capitalize">{type}</span>
                <span className="text-sm font-medium">{count}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="bg-gray-800 rounded-lg border border-gray-700 p-6">
          <h3 className="text-sm font-medium text-gray-400 mb-2">System Health</h3>
          <div className="space-y-2">
            <div className="flex justify-between items-center">
              <span className="text-sm">Total Executions</span>
              <span className="text-sm font-medium">{pluginStats?.total_executions || 0}</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm">Total Errors</span>
              <span className="text-sm font-medium text-red-400">{pluginStats?.total_errors || 0}</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm">Avg Priority</span>
              <span className="text-sm font-medium">{memoryStats?.average_priority?.toFixed(1) || '0.0'}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
