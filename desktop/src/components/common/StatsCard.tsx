import React from 'react'
import { LucideIcon } from 'lucide-react'

interface StatsCardProps {
  title: string
  value: string | number
  subtitle?: string
  icon: LucideIcon
  trend?: {
    value: number
    isPositive: boolean
  }
  color?: 'blue' | 'green' | 'yellow' | 'red' | 'purple'
}

const colorClasses = {
  blue: 'bg-blue-500/10 text-blue-500 border-blue-500/20',
  green: 'bg-green-500/10 text-green-500 border-green-500/20',
  yellow: 'bg-yellow-500/10 text-yellow-500 border-yellow-500/20',
  red: 'bg-red-500/10 text-red-500 border-red-500/20',
  purple: 'bg-purple-500/10 text-purple-500 border-purple-500/20',
}

export const StatsCard: React.FC<StatsCardProps> = ({
  title,
  value,
  subtitle,
  icon: Icon,
  trend,
  color = 'blue'
}) => {
  return (
    <div className="bg-gray-800 rounded-lg p-6 border border-gray-700 hover:border-gray-600 transition-colors">
      <div className="flex items-center justify-between">
        <div className="flex-1">
          <p className="text-sm font-medium text-gray-400">{title}</p>
          <p className="mt-2 text-3xl font-semibold text-white">{value}</p>
          {subtitle && (
            <p className="mt-1 text-sm text-gray-500">{subtitle}</p>
          )}
          {trend && (
            <div className="mt-2 flex items-center text-sm">
              <span className={trend.isPositive ? 'text-green-500' : 'text-red-500'}>
                {trend.isPositive ? '↑' : '↓'} {Math.abs(trend.value)}%
              </span>
              <span className="ml-2 text-gray-500">from yesterday</span>
            </div>
          )}
        </div>
        <div className={`p-3 rounded-lg ${colorClasses[color]}`}>
          <Icon className="w-6 h-6" />
        </div>
      </div>
    </div>
  )
}
