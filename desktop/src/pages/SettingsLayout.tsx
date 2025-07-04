import React from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import { Brain, Key } from 'lucide-react'

export const SettingsLayout: React.FC = () => {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Settings</h1>
        <p className="text-gray-400 mt-1">Configure system preferences</p>
      </div>

      {/* Tab Navigation */}
      <div className="border-b border-gray-700">
        <nav className="-mb-px flex space-x-8">
          <NavLink
            to="/settings/models"
            className={({ isActive }) =>
              `py-2 px-1 border-b-2 font-medium text-sm transition-colors ${
                isActive
                  ? 'border-blue-500 text-blue-500'
                  : 'border-transparent text-gray-400 hover:text-white hover:border-gray-300'
              }`
            }
          >
            <div className="flex items-center gap-2">
              <Brain className="w-4 h-4" />
              Model Settings
            </div>
          </NavLink>
          <NavLink
            to="/settings/auth"
            className={({ isActive }) =>
              `py-2 px-1 border-b-2 font-medium text-sm transition-colors ${
                isActive
                  ? 'border-blue-500 text-blue-500'
                  : 'border-transparent text-gray-400 hover:text-white hover:border-gray-300'
              }`
            }
          >
            <div className="flex items-center gap-2">
              <Key className="w-4 h-4" />
              Authentication
            </div>
          </NavLink>
        </nav>
      </div>

      {/* Settings Content */}
      <div>
        <Outlet />
      </div>
    </div>
  )
}
