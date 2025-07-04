import { createSlice, PayloadAction, createAsyncThunk } from '@reduxjs/toolkit'

interface AuthState {
  token: string | null
  isAuthenticated: boolean
  rememberInKeychain: boolean
  loading: boolean
  error: string | null
}

const initialState: AuthState = {
  token: null,
  isAuthenticated: false,
  rememberInKeychain: true,
  loading: true,
  error: null,
}

// Load token from keychain
export const loadToken = createAsyncThunk(
  'auth/loadToken',
  async () => {
    try {
      const token = await window.titanAPI.secureStorage.getPassword('TitanDesktop', 'admin_token')
      return token
    } catch (error) {
      console.error('Failed to load token:', error)
      return null
    }
  }
)

// Save token to keychain
export const saveToken = createAsyncThunk(
  'auth/saveToken',
  async ({ token, remember }: { token: string; remember: boolean }) => {
    if (remember) {
      await window.titanAPI.secureStorage.setPassword('TitanDesktop', 'admin_token', token)
    }
    return { token, remember }
  }
)

// Clear token from keychain
export const clearToken = createAsyncThunk(
  'auth/clearToken',
  async () => {
    await window.titanAPI.secureStorage.deletePassword('TitanDesktop', 'admin_token')
  }
)

const authSlice = createSlice({
  name: 'auth',
  initialState,
  reducers: {
    setToken: (state, action: PayloadAction<string>) => {
      state.token = action.payload
      state.isAuthenticated = true
      state.error = null
    },
    logout: (state) => {
      state.token = null
      state.isAuthenticated = false
    },
    setRememberInKeychain: (state, action: PayloadAction<boolean>) => {
      state.rememberInKeychain = action.payload
    },
  },
  extraReducers: (builder) => {
    builder
      // Load token
      .addCase(loadToken.pending, (state) => {
        state.loading = true
      })
      .addCase(loadToken.fulfilled, (state, action) => {
        state.loading = false
        if (action.payload) {
          state.token = action.payload
          state.isAuthenticated = true
        }
      })
      .addCase(loadToken.rejected, (state) => {
        state.loading = false
      })
      // Save token
      .addCase(saveToken.fulfilled, (state, action) => {
        state.token = action.payload.token
        state.isAuthenticated = true
        state.rememberInKeychain = action.payload.remember
      })
      // Clear token
      .addCase(clearToken.fulfilled, (state) => {
        state.token = null
        state.isAuthenticated = false
      })
  },
})

export const { setToken, logout, setRememberInKeychain } = authSlice.actions
export default authSlice.reducer
