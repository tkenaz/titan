import React from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { useAppSelector, useAppDispatch } from '../../hooks/redux'
import { toggleTheme } from '../../store/slices/uiSlice'
import { useGetCostStatsQuery } from '../../api/memoryApi'
import { useGetModelPreferencesQuery, useGetModelsQuery } from '../../api/gatewayApi'
import { 
  Brain, 
  MemoryStick, 
  Puzzle, 
  Target, 
  Settings, 
  Moon, 
  Sun,
  DollarSign,
  ChevronDown
} from 'lucide-react'

const DAILY_BUDGET = 100 // $100 daily budget

export const Header: React.FC = () => {
  const navigate = useNavigate()
  const location = useLocation()
  const dispatch = useAppDispatch()
  const theme = useAppSelector((state) => state.ui.theme)
  const { data: costStats } = useGetCostStatsQuery({ days: 1 })
  const { data: models } = useGetModelsQuery()
  const { data: preferences } = useGetModelPreferencesQuery()

  // Calculate today's spending
  const todaySpending = costStats?.daily_costs?.[0]?.cost || 0
  const budgetPercentage = (todaySpending / DAILY_BUDGET) * 100
  const budgetColor = budgetPercentage < 50 ? 'text-green-500' : 
                      budgetPercentage < 90 ? 'text-yellow-500' : 'text-red-500'

  const navigation = [
    { name: 'Dashboard', href: '/dashboard', icon: Brain },
    { name: 'Memory', href: '/memory', icon: MemoryStick },
    { name: 'Plugins', href: '/plugins', icon: Puzzle },
    { name: 'Goals', href: '/goals', icon: Target },
    { name: 'Settings', href: '/settings/models', icon: Settings },
  ]

  const currentModel = models?.find(m => m.id === preferences?.default_model)

  return (
    <header className="bg-gray-900 border-b border-gray-800">
      <div className="px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Logo and Navigation */}
          <div className="flex items-center">
            <div className="flex-shrink-0">
              <h1 className="text-2xl font-bold text-white">TITAN</h1>
            </div>
            <nav className="hidden md:ml-10 md:flex md:space-x-4">
              {navigation.map((item) => {
                const Icon = item.icon
                const isActive = location.pathname.startsWith(item.href)
                return (
                  <button
                    key={item.name}
                    onClick={() => navigate(item.href)}
                    className={`
                      px-3 py-2 rounded-md text-sm font-medium flex items-center gap-2
                      transition-colors duration-200
                      ${isActive 
                        ? 'bg-gray-800 text-white' 
                        : 'text-gray-300 hover:bg-gray-800 hover:text-white'
                      }
                    `}
                  >
                    <Icon className="w-4 h-4" />
                    {item.name}
                  </button>
                )
              })}
            </nav>
          </div>

          {/* Right side - Budget, Model, Theme */}
          <div className="flex items-center gap-4">
            {/* Budget Meter */}
            <div className="flex items-center gap-2">
              <DollarSign className={`w-4 h-4 ${budgetColor}`} />
              <div className="flex flex-col items-end">
                <span className={`text-sm font-medium ${budgetColor}`}>
                  ${todaySpending.toFixed(2)} / ${DAILY_BUDGET}
                </span>
                <div className="w-32 h-2 bg-gray-700 rounded-full overflow-hidden">
                  <div 
                    className={`h-full transition-all duration-300 ${
                      budgetPercentage < 50 ? 'bg-green-500' :
                      budgetPercentage < 90 ? 'bg-yellow-500' : 'bg-red-500'
                    }`}
                    style={{ width: `${Math.min(budgetPercentage, 100)}%` }}
                  />
                </div>
              </div>
            </div>

            {/* Model Selector */}
            <div className="relative">
              <button className="flex items-center gap-2 px-3 py-2 text-sm bg-gray-800 text-gray-300 rounded-md hover:bg-gray-700 transition-colors">
                <span className="font-medium">{currentModel?.name || 'Select Model'}</span>
                {currentModel && (
                  <span className="text-xs text-gray-500">
                    ${currentModel.output_price_per_1k}/1k
                  </span>
                )}
                <ChevronDown className="w-4 h-4" />
              </button>
            </div>

            {/* Theme Toggle */}
            <button
              onClick={() => dispatch(toggleTheme())}
              className="p-2 text-gray-400 hover:text-white transition-colors"
              aria-label="Toggle theme"
            >
              {theme === 'dark' ? (
                <Sun className="w-5 h-5" />
              ) : (
                <Moon className="w-5 h-5" />
              )}
            </button>
          </div>
        </div>
      </div>
    </header>
  )
}
