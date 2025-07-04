import React, { useState, useEffect, useRef } from 'react'
import { Search, X } from 'lucide-react'

interface SearchBarProps {
  value: string
  onChange: (value: string) => void
  onSubmit?: () => void
  placeholder?: string
  showHistory?: boolean
  className?: string
}

const SEARCH_HISTORY_KEY = 'titan-search-history'
const MAX_HISTORY_ITEMS = 10

export const SearchBar: React.FC<SearchBarProps> = ({
  value,
  onChange,
  onSubmit,
  placeholder = 'Search...',
  showHistory = true,
  className = ''
}) => {
  const [isFocused, setIsFocused] = useState(false)
  const [history, setHistory] = useState<string[]>([])
  const [showDropdown, setShowDropdown] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (showHistory) {
      const stored = localStorage.getItem(SEARCH_HISTORY_KEY)
      if (stored) {
        setHistory(JSON.parse(stored))
      }
    }
  }, [showHistory])

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (value.trim()) {
      // Add to history
      if (showHistory) {
        const newHistory = [value, ...history.filter(h => h !== value)].slice(0, MAX_HISTORY_ITEMS)
        setHistory(newHistory)
        localStorage.setItem(SEARCH_HISTORY_KEY, JSON.stringify(newHistory))
      }
      onSubmit?.()
      setShowDropdown(false)
    }
  }

  const handleHistoryClick = (item: string) => {
    onChange(item)
    setShowDropdown(false)
    inputRef.current?.focus()
  }

  const clearHistory = () => {
    setHistory([])
    localStorage.removeItem(SEARCH_HISTORY_KEY)
  }

  return (
    <div className={`relative ${className}`}>
      <form onSubmit={handleSubmit}>
        <div className="relative">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-gray-400" />
          <input
            ref={inputRef}
            type="text"
            value={value}
            onChange={(e) => onChange(e.target.value)}
            onFocus={() => {
              setIsFocused(true)
              setShowDropdown(true)
            }}
            onBlur={() => {
              setIsFocused(false)
              // Delay to allow click on dropdown items
              setTimeout(() => setShowDropdown(false), 200)
            }}
            placeholder={placeholder}
            className={`
              w-full pl-10 pr-10 py-2 bg-gray-800 border rounded-lg
              text-white placeholder-gray-400
              focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent
              transition-all duration-200
              ${isFocused ? 'border-gray-600' : 'border-gray-700'}
            `}
          />
          {value && (
            <button
              type="button"
              onClick={() => onChange('')}
              className="absolute right-3 top-1/2 transform -translate-y-1/2 text-gray-400 hover:text-white transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          )}
        </div>
      </form>

      {/* Search History Dropdown */}
      {showHistory && showDropdown && history.length > 0 && (
        <div className="absolute z-10 w-full mt-1 bg-gray-800 border border-gray-700 rounded-lg shadow-lg overflow-hidden">
          <div className="flex items-center justify-between px-3 py-2 border-b border-gray-700">
            <span className="text-xs text-gray-400 uppercase">Recent Searches</span>
            <button
              onClick={clearHistory}
              className="text-xs text-gray-500 hover:text-white transition-colors"
            >
              Clear
            </button>
          </div>
          <div className="max-h-60 overflow-y-auto">
            {history.map((item, index) => (
              <button
                key={index}
                onClick={() => handleHistoryClick(item)}
                className="w-full px-3 py-2 text-left text-sm text-gray-300 hover:bg-gray-700 transition-colors"
              >
                {item}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
