import React from 'react'
import ReactDOM from 'react-dom/client'
import { Provider } from 'react-redux'
import { RouterProvider, createBrowserRouter, Navigate } from 'react-router-dom'
import { store } from './store'
import { Layout } from './components/Layout'
import { Dashboard } from './pages/Dashboard'
import { MemoryExplorer } from './pages/MemoryExplorer'
import { PluginCenter } from './pages/PluginCenter'
import { GoalManager } from './pages/GoalManager'
import { ModelSettings } from './pages/ModelSettings'
import { AuthSettings } from './pages/AuthSettings'
import { DebugPage } from './pages/DebugPage'
import { SettingsLayout } from './pages/SettingsLayout'
import './index.css'

// Create router
const router = createBrowserRouter([
  {
    path: '/',
    element: <Layout />,
    children: [
      {
        index: true,
        element: <Navigate to="/dashboard" replace />
      },
      {
        path: 'dashboard',
        element: <Dashboard />
      },
      {
        path: 'memory',
        element: <MemoryExplorer />
      },
      {
        path: 'plugins',
        element: <PluginCenter />
      },
      {
        path: 'goals',
        element: <GoalManager />
      },
      {
        path: 'debug',
        element: <DebugPage />
      },
      {
        path: 'settings',
        element: <SettingsLayout />,
        children: [
          {
            index: true,
            element: <Navigate to="/settings/models" replace />
          },
          {
            path: 'models',
            element: <ModelSettings />
          },
          {
            path: 'auth',
            element: <AuthSettings />
          }
        ]
      }
    ]
  }
])

// Initialize app
const initializeApp = async () => {
  // Check for saved token in secure storage
  if (window.electronAPI) {
    try {
      const savedToken = await window.electronAPI.getSecureValue('admin_token')
      if (savedToken) {
        store.dispatch({ type: 'auth/setToken', payload: savedToken })
        store.dispatch({ type: 'auth/setRememberInKeychain', payload: true })
      }
    } catch (error) {
      console.error('Failed to retrieve saved token:', error)
    }
  }

  // Start WebSocket connection
  store.dispatch({ type: 'websocket/connect' })
}

// Render app
ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <Provider store={store}>
      <RouterProvider router={router} />
    </Provider>
  </React.StrictMode>
)

// Initialize after render
initializeApp()
