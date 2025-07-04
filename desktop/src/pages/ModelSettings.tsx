import React, { useState } from 'react'
import { 
  Brain, 
  DollarSign, 
  Zap, 
  Clock,
  ChevronDown,
  Save
} from 'lucide-react'
import { 
  useGetModelsQuery, 
  useGetModelPreferencesQuery,
  useUpdateModelPreferencesMutation,
  Model
} from '../api/gatewayApi'

interface ModelCardProps {
  model: Model
  isSelected: boolean
  onSelect: () => void
}

const ModelCard: React.FC<ModelCardProps> = ({ model, isSelected, onSelect }) => {
  return (
    <div 
      onClick={onSelect}
      className={`
        bg-gray-800 rounded-lg border-2 p-6 cursor-pointer transition-all
        ${isSelected 
          ? 'border-blue-500 shadow-lg shadow-blue-500/20' 
          : 'border-gray-700 hover:border-gray-600'
        }
      `}
    >
      <div className="flex items-start justify-between mb-4">
        <div>
          <h3 className="text-lg font-semibold text-white">{model.name}</h3>
          <p className="text-sm text-gray-400 capitalize">{model.provider}</p>
        </div>
        <div className={`
          w-4 h-4 rounded-full border-2 
          ${isSelected ? 'bg-blue-500 border-blue-500' : 'border-gray-600'}
        `} />
      </div>

      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <span className="text-sm text-gray-400 flex items-center gap-1">
            <DollarSign className="w-3 h-3" />
            Input
          </span>
          <span className="text-sm font-medium">${model.input_price_per_1k}/1k</span>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-sm text-gray-400 flex items-center gap-1">
            <DollarSign className="w-3 h-3" />
            Output
          </span>
          <span className="text-sm font-medium">${model.output_price_per_1k}/1k</span>
        </div>
        {model.cache_price_per_1k && (
          <div className="flex items-center justify-between">
            <span className="text-sm text-gray-400 flex items-center gap-1">
              <DollarSign className="w-3 h-3" />
              Cache
            </span>
            <span className="text-sm font-medium">${model.cache_price_per_1k}/1k</span>
          </div>
        )}
        <div className="flex items-center justify-between">
          <span className="text-sm text-gray-400 flex items-center gap-1">
            <Clock className="w-3 h-3" />
            Latency
          </span>
          <span className="text-sm font-medium">{model.average_latency_ms}ms</span>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-sm text-gray-400 flex items-center gap-1">
            <Zap className="w-3 h-3" />
            Max Tokens
          </span>
          <span className="text-sm font-medium">{model.max_tokens.toLocaleString()}</span>
        </div>
      </div>

      {model.recommended_for.length > 0 && (
        <div className="mt-4 pt-4 border-t border-gray-700">
          <p className="text-xs text-gray-400 mb-2">Recommended for:</p>
          <div className="flex flex-wrap gap-1">
            {model.recommended_for.map((use, index) => (
              <span key={index} className="text-xs bg-gray-700 px-2 py-1 rounded">
                {use}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

export const ModelSettings: React.FC = () => {
  const { data: models, isLoading: modelsLoading } = useGetModelsQuery()
  const { data: preferences, isLoading: prefsLoading } = useGetModelPreferencesQuery()
  const [updatePreferences, { isLoading: updating }] = useUpdateModelPreferencesMutation()
  
  const [selectedDefault, setSelectedDefault] = useState<string>('')
  const [taskModels, setTaskModels] = useState<Record<string, string>>({})
  const [hasChanges, setHasChanges] = useState(false)

  React.useEffect(() => {
    if (preferences) {
      setSelectedDefault(preferences.default_model)
      setTaskModels(preferences.task_models)
    }
  }, [preferences])

  const handleSave = async () => {
    try {
      await updatePreferences({
        default_model: selectedDefault,
        task_models: taskModels
      }).unwrap()
      setHasChanges(false)
    } catch (error) {
      console.error('Failed to update preferences:', error)
    }
  }

  const handleDefaultChange = (modelId: string) => {
    setSelectedDefault(modelId)
    setHasChanges(true)
  }

  const handleTaskModelChange = (task: string, modelId: string) => {
    setTaskModels(prev => ({ ...prev, [task]: modelId }))
    setHasChanges(true)
  }

  if (modelsLoading || prefsLoading) {
    return (
      <div className="flex justify-center py-12">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-white"></div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Model Settings</h1>
          <p className="text-gray-400 mt-1">Configure AI model preferences and defaults</p>
        </div>
        {hasChanges && (
          <button
            onClick={handleSave}
            disabled={updating}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-800 text-white rounded-lg transition-colors flex items-center gap-2"
          >
            <Save className="h-4 w-4" />
            {updating ? 'Saving...' : 'Save Changes'}
          </button>
        )}
      </div>

      {/* Default Model Selection */}
      <div>
        <h2 className="text-xl font-semibold mb-4">Default Model</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {models?.map((model) => (
            <ModelCard
              key={model.id}
              model={model}
              isSelected={selectedDefault === model.id}
              onSelect={() => handleDefaultChange(model.id)}
            />
          ))}
        </div>
      </div>

      {/* Task-Specific Models */}
      <div>
        <h2 className="text-xl font-semibold mb-4">Task-Specific Models</h2>
        <div className="bg-gray-800 rounded-lg border border-gray-700 p-6">
          <div className="space-y-4">
            {Object.entries({
              self_reflection: 'Self-Reflection & Analysis',
              vitals_check: 'System Vitals Check',
              experiment: 'Experiments & Research',
              general: 'General Tasks'
            }).map(([task, label]) => (
              <div key={task} className="flex items-center justify-between">
                <span className="text-sm font-medium text-gray-300">{label}</span>
                <div className="relative">
                  <select
                    value={taskModels[task] || selectedDefault}
                    onChange={(e) => handleTaskModelChange(task, e.target.value)}
                    className="appearance-none bg-gray-700 border border-gray-600 rounded-lg px-4 py-2 pr-8 text-sm text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                  >
                    <option value="">Use Default</option>
                    {models?.map((model) => (
                      <option key={model.id} value={model.id}>
                        {model.name} (${model.output_price_per_1k}/1k)
                      </option>
                    ))}
                  </select>
                  <ChevronDown className="absolute right-2 top-1/2 transform -translate-y-1/2 w-4 h-4 text-gray-400 pointer-events-none" />
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Model Comparison */}
      <div>
        <h2 className="text-xl font-semibold mb-4">Model Comparison</h2>
        <div className="bg-gray-800 rounded-lg border border-gray-700 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-700">
              <thead className="bg-gray-900">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">
                    Model
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">
                    Provider
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">
                    Input $/1k
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">
                    Output $/1k
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">
                    Max Tokens
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">
                    Avg Latency
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-700">
                {models?.map((model) => (
                  <tr key={model.id} className="hover:bg-gray-700 transition-colors">
                    <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-white">
                      {model.name}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-300 capitalize">
                      {model.provider}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-300">
                      ${model.input_price_per_1k}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-300">
                      ${model.output_price_per_1k}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-300">
                      {model.max_tokens.toLocaleString()}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-300">
                      {model.average_latency_ms}ms
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  )
}
