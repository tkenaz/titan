import React, { useState } from 'react'
import { 
  Play, 
  RefreshCw, 
  Power, 
  AlertCircle, 
  CheckCircle,
  Terminal,
  Zap
} from 'lucide-react'
import { DataTable } from '../components/common/DataTable'
import { 
  useGetPluginsQuery,
  useTogglePluginMutation,
  useReloadPluginMutation,
  useExecutePluginMutation,
  useGetPluginLogsQuery,
  Plugin
} from '../api/pluginsApi'

interface PluginLogsModalProps {
  plugin: Plugin
  onClose: () => void
}

const PluginLogsModal: React.FC<PluginLogsModalProps> = ({ plugin, onClose }) => {
  const { data: logs, isLoading, refetch } = useGetPluginLogsQuery({ 
    name: plugin.name, 
    tail: 2000 
  })

  return (
    <div className="fixed inset-0 z-50 overflow-hidden">
      <div className="absolute inset-0 bg-black bg-opacity-50" onClick={onClose} />
      <div className="absolute inset-0 flex items-center justify-center p-4">
        <div className="bg-gray-800 rounded-lg shadow-xl max-w-4xl w-full max-h-[80vh] flex flex-col">
          <div className="flex items-center justify-between border-b border-gray-700 px-6 py-4">
            <h2 className="text-lg font-semibold flex items-center gap-2">
              <Terminal className="h-5 w-5" />
              {plugin.name} Logs
            </h2>
            <button
              onClick={onClose}
              className="text-gray-400 hover:text-white transition-colors"
            >
              ✕
            </button>
          </div>

          <div className="flex-1 overflow-auto p-6">
            {isLoading ? (
              <div className="flex justify-center py-8">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-white"></div>
              </div>
            ) : (
              <pre className="text-xs text-gray-300 font-mono whitespace-pre-wrap">
                {logs || 'No logs available'}
              </pre>
            )}
          </div>

          <div className="border-t border-gray-700 px-6 py-4 flex justify-end gap-3">
            <button
              onClick={() => refetch()}
              className="px-4 py-2 text-sm bg-gray-700 hover:bg-gray-600 text-white rounded-lg transition-colors flex items-center gap-2"
            >
              <RefreshCw className="h-4 w-4" />
              Refresh
            </button>
            <button
              onClick={onClose}
              className="px-4 py-2 text-sm bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors"
            >
              Close
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

export const PluginCenter: React.FC = () => {
  const { data: plugins, isLoading } = useGetPluginsQuery()
  const [togglePlugin] = useTogglePluginMutation()
  const [reloadPlugin] = useReloadPluginMutation()
  const [executePlugin] = useExecutePluginMutation()
  const [selectedPlugin, setSelectedPlugin] = useState<Plugin | null>(null)

  const handleToggle = async (plugin: Plugin) => {
    try {
      await togglePlugin({ 
        name: plugin.name, 
        enabled: plugin.state === 'inactive' 
      }).unwrap()
    } catch (error) {
      console.error('Failed to toggle plugin:', error)
    }
  }

  const handleReload = async (plugin: Plugin) => {
    try {
      await reloadPlugin(plugin.name).unwrap()
    } catch (error) {
      console.error('Failed to reload plugin:', error)
    }
  }

  const handleExecute = async (plugin: Plugin) => {
    try {
      await executePlugin({ name: plugin.name }).unwrap()
    } catch (error) {
      console.error('Failed to execute plugin:', error)
    }
  }

  const getStateIcon = (state: string) => {
    switch (state) {
      case 'active':
        return <CheckCircle className="h-4 w-4 text-green-500" />
      case 'failed':
        return <AlertCircle className="h-4 w-4 text-red-500" />
      case 'loading':
        return <RefreshCw className="h-4 w-4 text-yellow-500 animate-spin" />
      default:
        return <Power className="h-4 w-4 text-gray-500" />
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Plugin Center</h1>
        <p className="text-gray-400 mt-1">Manage and monitor system plugins</p>
      </div>

      <DataTable
        data={plugins || []}
        loading={isLoading}
        columns={[
          {
            key: 'name',
            label: 'Plugin',
            render: (plugin) => (
              <div>
                <p className="font-medium text-white">{plugin.name}</p>
                {plugin.description && (
                  <p className="text-xs text-gray-400 mt-1">{plugin.description}</p>
                )}
              </div>
            )
          },
          {
            key: 'state',
            label: 'State',
            render: (plugin) => (
              <div className="flex items-center gap-2">
                {getStateIcon(plugin.state)}
                <span className={`text-sm capitalize ${
                  plugin.state === 'active' ? 'text-green-500' :
                  plugin.state === 'failed' ? 'text-red-500' :
                  plugin.state === 'loading' ? 'text-yellow-500' :
                  'text-gray-500'
                }`}>
                  {plugin.state}
                </span>
              </div>
            )
          },
          {
            key: 'version',
            label: 'Version',
            render: (plugin) => (
              <span className="text-sm text-gray-400">{plugin.version}</span>
            )
          },
          {
            key: 'last_run',
            label: 'Last Run',
            render: (plugin) => (
              <span className="text-sm text-gray-400">
                {plugin.last_run ? new Date(plugin.last_run).toLocaleString() : 'Never'}
              </span>
            )
          },
          {
            key: 'error_count',
            label: 'Errors',
            render: (plugin) => (
              <div>
                <span className={`text-sm ${plugin.error_count > 0 ? 'text-red-400' : 'text-gray-400'}`}>
                  {plugin.error_count}
                </span>
                {plugin.last_error && (
                  <p className="text-xs text-red-400 truncate max-w-xs mt-1">
                    {plugin.last_error}
                  </p>
                )}
              </div>
            )
          },
          {
            key: 'actions',
            label: 'Actions',
            render: (plugin) => (
              <div className="flex items-center gap-2">
                <button
                  onClick={() => handleExecute(plugin)}
                  disabled={plugin.state !== 'active'}
                  className="p-2 text-gray-400 hover:text-white disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                  title="Run Now"
                >
                  <Play className="h-4 w-4" />
                </button>
                <button
                  onClick={() => handleReload(plugin)}
                  className="p-2 text-gray-400 hover:text-white transition-colors"
                  title="Reload"
                >
                  <RefreshCw className="h-4 w-4" />
                </button>
                <button
                  onClick={() => handleToggle(plugin)}
                  className={`p-2 transition-colors ${
                    plugin.state === 'active' 
                      ? 'text-green-500 hover:text-green-400' 
                      : 'text-gray-400 hover:text-white'
                  }`}
                  title={plugin.state === 'active' ? 'Disable' : 'Enable'}
                >
                  <Power className="h-4 w-4" />
                </button>
                <button
                  onClick={() => setSelectedPlugin(plugin)}
                  className="p-2 text-gray-400 hover:text-white transition-colors"
                  title="View Logs"
                >
                  <Terminal className="h-4 w-4" />
                </button>
              </div>
            )
          }
        ]}
      />

      {/* Plugin capabilities */}
      {plugins && plugins.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {plugins.map((plugin) => (
            <div key={plugin.name} className="bg-gray-800 rounded-lg border border-gray-700 p-6">
              <h3 className="text-lg font-semibold mb-3 flex items-center gap-2">
                <Zap className="h-5 w-5 text-yellow-500" />
                {plugin.name} Capabilities
              </h3>
              <div className="space-y-2">
                {plugin.capabilities.length > 0 ? (
                  plugin.capabilities.map((capability, index) => (
                    <div key={index} className="flex items-center gap-2">
                      <CheckCircle className="h-4 w-4 text-green-500 flex-shrink-0" />
                      <span className="text-sm text-gray-300">{capability}</span>
                    </div>
                  ))
                ) : (
                  <p className="text-sm text-gray-500">No capabilities defined</p>
                )}
              </div>
              
              {plugin.config && Object.keys(plugin.config).length > 0 && (
                <div className="mt-4 pt-4 border-t border-gray-700">
                  <h4 className="text-sm font-medium text-gray-400 mb-2">Configuration</h4>
                  <pre className="text-xs bg-gray-900 p-3 rounded overflow-x-auto">
                    {JSON.stringify(plugin.config, null, 2)}
                  </pre>
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Logs Modal */}
      {selectedPlugin && (
        <PluginLogsModal
          plugin={selectedPlugin}
          onClose={() => setSelectedPlugin(null)}
        />
      )}
    </div>
  )
}
