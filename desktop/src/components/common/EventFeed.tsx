import React, { useEffect, useRef } from 'react'
import { useAppSelector } from '../../hooks/redux'
import { Activity, AlertCircle, CheckCircle, XCircle, Zap } from 'lucide-react'
import { format } from 'date-fns'

interface EventItemProps {
  event: {
    id: string
    type: string
    timestamp: string
    data: any
  }
}

const EventItem: React.FC<EventItemProps> = ({ event }) => {
  const getEventIcon = () => {
    if (event.type.includes('error')) return <XCircle className="w-4 h-4 text-red-500" />
    if (event.type.includes('success')) return <CheckCircle className="w-4 h-4 text-green-500" />
    if (event.type.includes('model')) return <Zap className="w-4 h-4 text-blue-500" />
    if (event.type.includes('plugin')) return <Activity className="w-4 h-4 text-purple-500" />
    return <AlertCircle className="w-4 h-4 text-yellow-500" />
  }

  const getEventTitle = () => {
    const typeMap: Record<string, string> = {
      'model.request': 'Model Request',
      'model.response': 'Model Response',
      'plugin.executed': 'Plugin Executed',
      'plugin.error': 'Plugin Error',
      'goal.started': 'Goal Started',
      'goal.finished': 'Goal Finished',
      'memory.stored': 'Memory Stored',
      'memory.searched': 'Memory Searched',
    }
    return typeMap[event.type] || event.type
  }

  const getEventDetails = () => {
    switch (event.type) {
      case 'model.request':
        return `${event.data.model} - ${event.data.tokens || 0} tokens`
      case 'model.response':
        return `Cost: $${event.data.cost?.toFixed(4) || '0.0000'} - ${event.data.latency_ms || 0}ms`
      case 'plugin.executed':
        return `${event.data.plugin} - ${event.data.status}`
      case 'plugin.error':
        return `${event.data.plugin}: ${event.data.error}`
      case 'goal.finished':
        return `${event.data.goal_id} - ${event.data.status}`
      default:
        return JSON.stringify(event.data)
    }
  }

  return (
    <div className="flex items-start gap-3 p-3 hover:bg-gray-700/50 transition-colors">
      <div className="mt-0.5">{getEventIcon()}</div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-white">{getEventTitle()}</span>
          <span className="text-xs text-gray-500">
            {format(new Date(event.timestamp), 'HH:mm:ss')}
          </span>
        </div>
        <p className="text-xs text-gray-400 truncate">{getEventDetails()}</p>
      </div>
    </div>
  )
}

interface EventFeedProps {
  maxHeight?: string
  className?: string
}

export const EventFeed: React.FC<EventFeedProps> = ({ 
  maxHeight = '400px',
  className = '' 
}) => {
  const events = useAppSelector((state) => state.events?.events || [])
  const containerRef = useRef<HTMLDivElement>(null)

  // Auto-scroll to bottom when new events arrive
  useEffect(() => {
    if (containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight
    }
  }, [events])

  return (
    <div className={`bg-gray-800 rounded-lg border border-gray-700 ${className}`}>
      <div className="px-4 py-3 border-b border-gray-700">
        <h3 className="text-sm font-medium text-white flex items-center gap-2">
          <Activity className="w-4 h-4" />
          Real-time Events
        </h3>
      </div>
      <div
        ref={containerRef}
        className="overflow-y-auto divide-y divide-gray-700"
        style={{ maxHeight }}
      >
        {events.length === 0 ? (
          <div className="p-8 text-center text-gray-500">
            <Activity className="w-8 h-8 mx-auto mb-2 opacity-50" />
            <p className="text-sm">Waiting for events...</p>
          </div>
        ) : (
          events.map((event, index) => (
            <EventItem key={event.id || `event-${index}`} event={{ 
              id: event.id || `event-${index}`,
              ...event 
            }} />
          ))
        )}
      </div>
    </div>
  )
}
