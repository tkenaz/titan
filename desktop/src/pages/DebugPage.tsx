import React from 'react'
import { useAppSelector } from '../hooks/redux'

export const DebugPage: React.FC = () => {
  const auth = useAppSelector((state) => state.auth)
  const events = useAppSelector((state) => state.events)
  const ui = useAppSelector((state) => state.ui)

  return (
    <div className="p-8 space-y-6">
      <h1 className="text-2xl font-bold">Debug Information</h1>
      
      <div className="bg-gray-800 rounded-lg p-6">
        <h2 className="text-lg font-semibold mb-4">Auth State</h2>
        <pre className="text-xs bg-gray-900 p-4 rounded overflow-auto">
          {JSON.stringify(auth, null, 2)}
        </pre>
      </div>

      <div className="bg-gray-800 rounded-lg p-6">
        <h2 className="text-lg font-semibold mb-4">Events State</h2>
        <pre className="text-xs bg-gray-900 p-4 rounded overflow-auto">
          {JSON.stringify(events, null, 2)}
        </pre>
      </div>

      <div className="bg-gray-800 rounded-lg p-6">
        <h2 className="text-lg font-semibold mb-4">UI State</h2>
        <pre className="text-xs bg-gray-900 p-4 rounded overflow-auto">
          {JSON.stringify(ui, null, 2)}
        </pre>
      </div>

      <div className="bg-gray-800 rounded-lg p-6">
        <h2 className="text-lg font-semibold mb-4">Window APIs</h2>
        <pre className="text-xs bg-gray-900 p-4 rounded overflow-auto">
          {JSON.stringify({
            electronAPI: typeof window.electronAPI,
            titanAPI: typeof window.titanAPI,
            location: window.location.href
          }, null, 2)}
        </pre>
      </div>

      <div className="bg-gray-800 rounded-lg p-6">
        <h2 className="text-lg font-semibold mb-4">Backend Status</h2>
        <div className="space-y-2">
          <div>Memory Service (8001): <span id="memory-status">Checking...</span></div>
          <div>Plugin Manager (8003): <span id="plugin-status">Checking...</span></div>
          <div>Goal Scheduler (8004): <span id="goal-status">Checking...</span></div>
          <div>Model Gateway (8081): <span id="gateway-status">Checking...</span></div>
        </div>
      </div>
    </div>
  )
}
