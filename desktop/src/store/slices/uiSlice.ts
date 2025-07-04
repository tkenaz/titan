import { createSlice, PayloadAction } from '@reduxjs/toolkit'

interface UIState {
  theme: 'light' | 'dark'
  sidebarCollapsed: boolean
  backendOnline: boolean
  searchHistory: string[]
}

const initialState: UIState = {
  theme: 'dark',
  sidebarCollapsed: false,
  backendOnline: true,
  searchHistory: JSON.parse(localStorage.getItem('searchHistory') || '[]'),
}

const uiSlice = createSlice({
  name: 'ui',
  initialState,
  reducers: {
    toggleTheme: (state) => {
      state.theme = state.theme === 'dark' ? 'light' : 'dark'
      localStorage.setItem('theme', state.theme)
      if (state.theme === 'dark') {
        document.documentElement.classList.add('dark')
      } else {
        document.documentElement.classList.remove('dark')
      }
    },
    setTheme: (state, action: PayloadAction<'light' | 'dark'>) => {
      state.theme = action.payload
      localStorage.setItem('theme', action.payload)
      if (action.payload === 'dark') {
        document.documentElement.classList.add('dark')
      } else {
        document.documentElement.classList.remove('dark')
      }
    },
    toggleSidebar: (state) => {
      state.sidebarCollapsed = !state.sidebarCollapsed
    },
    setBackendOnline: (state, action: PayloadAction<boolean>) => {
      state.backendOnline = action.payload
    },
    addSearchHistory: (state, action: PayloadAction<string>) => {
      // Add to beginning and keep only last 10
      state.searchHistory = [
        action.payload,
        ...state.searchHistory.filter(q => q !== action.payload)
      ].slice(0, 10)
      localStorage.setItem('searchHistory', JSON.stringify(state.searchHistory))
    },
    clearSearchHistory: (state) => {
      state.searchHistory = []
      localStorage.removeItem('searchHistory')
    },
  },
})

export const {
  toggleTheme,
  setTheme,
  toggleSidebar,
  setBackendOnline,
  addSearchHistory,
  clearSearchHistory,
} = uiSlice.actions

export default uiSlice.reducer
