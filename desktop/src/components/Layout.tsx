import React from 'react'
import { Outlet, NavLink } from 'react-router-dom'
import { useAppSelector } from '../hooks/redux'
import { 
  Brain, 
  Database, 
  Puzzle, 
  Target, 
  Settings,
  Activity,
  AlertCircle,
  DollarSign
} from 'lucide-react'

export const Layout: React.FC = () => {
  const { connectionStatus, stats } = useAppSelector((state) => state.events)
  const { theme } = useAppSelector((state) => state.ui)
  
  const budgetPercentage = (stats.totalCost / 100) * 100 // Assuming $100 budget
  const budgetColor = budgetPercentage < 50 ? 'text-green-500' : 
                     budgetPercentage < 90 ? 'text-yellow-500' : 'text-red-500'

  const navItems = [
    { path: '/dashboard', icon: Activity, label: 'Dashboard' },
    { path: '/memory', icon: Database, label: 'Memory' },
    { path: '/plugins', icon: Puzzle, label: 'Plugins' },
    { path: '/goals', icon: Target, label: 'Goals' },
    { path: '/settings', icon: Settings, label: 'Settings' },
  ]

  return (
    <div className="min-h-screen bg-gray-900 text-gray-100 flex">
      {/* Sidebar */}
      <aside className="w-64 bg-gray-800 border-r border-gray-700">
        <div className="p-6">
          <div className="flex items-center space-x-3">
            <Brain className="h-8 w-8 text-blue-500" />
            <h1 className="text-xl font-bold">Titan</h1>
          </div>
        </div>
        
        <nav className="px-4 space-y-1">
          {navItems.map(({ path, icon: Icon, label }) => (
            <NavLink
              key={path}
              to={path}
              className={({ isActive }) =>
                `flex items-center space-x-3 px-4 py-3 rounded-lg transition-colors ${
                  isActive
                    ? 'bg-blue-600 text-white'
                    : 'text-gray-300 hover:bg-gray-700 hover:text-white'
                }`
              }
            >
              <Icon className="h-5 w-5" />
              <span>{label}</span>
            </NavLink>
          ))}
        </nav>
      </aside>

      {/* Main content */}
      <div className="flex-1 flex flex-col">
        {/* Header */}
        <header className="bg-gray-800 border-b border-gray-700 px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-6">
              {/* Connection status */}
              <div className="flex items-center space-x-2">
                <div className={`h-2 w-2 rounded-full ${
                  connectionStatus === 'connected' ? 'bg-green-500' : 
                  connectionStatus === 'error' ? 'bg-red-500' : 'bg-yellow-500'
                }`} />
                <span className="text-sm text-gray-400">
                  {connectionStatus === 'connected' ? 'Connected' : 
                   connectionStatus === 'error' ? 'Error' : 'Connecting...'}
                </span>
              </div>
              
              {/* Stats */}
              <div className="flex items-center space-x-4 text-sm">
                <div className="flex items-center space-x-1">
                  <Activity className="h-4 w-4 text-gray-400" />
                  <span>{stats.totalRequests} requests</span>
                </div>
                <div className="flex items-center space-x-1">
                  <Puzzle className="h-4 w-4 text-gray-400" />
                  <span>{stats.activePlugins} active</span>
                </div>
                <div className="flex items-center space-x-1">
                  <Target className="h-4 w-4 text-gray-400" />
                  <span>{stats.scheduledGoals} scheduled</span>
                </div>
              </div>
            </div>

            {/* Budget meter */}
            <div className="flex items-center space-x-3">
              <div className="flex items-center space-x-2">
                <DollarSign className={`h-4 w-4 ${budgetColor}`} />
                <span className={`text-sm font-medium ${budgetColor}`}>
                  ${stats.totalCost.toFixed(2)} / $100.00
                </span>
              </div>
              <div className="w-32 h-2 bg-gray-700 rounded-full overflow-hidden">
                <div 
                  className={`h-full transition-all ${
                    budgetPercentage < 50 ? 'bg-green-500' : 
                    budgetPercentage < 90 ? 'bg-yellow-500' : 'bg-red-500'
                  }`}
                  style={{ width: `${Math.min(budgetPercentage, 100)}%` }}
                />
              </div>
            </div>
          </div>
        </header>

        {/* Page content */}
        <main className="flex-1 p-6 overflow-auto">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
