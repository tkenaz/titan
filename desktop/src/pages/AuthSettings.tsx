import React, { useState } from 'react'
import { 
  Key, 
  Save, 
  Eye, 
  EyeOff,
  Shield,
  AlertCircle,
  CheckCircle
} from 'lucide-react'
import { useAppDispatch, useAppSelector } from '../hooks/redux'
import { setToken, setRememberInKeychain } from '../store/slices/authSlice'

export const AuthSettings: React.FC = () => {
  const dispatch = useAppDispatch()
  const { token, rememberInKeychain } = useAppSelector((state) => state.auth)
  
  const [adminToken, setAdminToken] = useState(token || '')
  const [showToken, setShowToken] = useState(false)
  const [remember, setRemember] = useState(rememberInKeychain)
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState('')

  const handleSave = async () => {
    setError('')
    setSaved(false)

    if (!adminToken.trim()) {
      setError('Token cannot be empty')
      return
    }

    try {
      // Update Redux store
      dispatch(setToken(adminToken))
      dispatch(setRememberInKeychain(remember))

      // If remember is enabled, save to secure storage
      if (remember && window.electronAPI) {
        await window.electronAPI.setSecureValue('admin_token', adminToken)
      } else if (!remember && window.electronAPI) {
        // Clear from secure storage if remember is disabled
        await window.electronAPI.deleteSecureValue('admin_token')
      }

      setSaved(true)
      setTimeout(() => setSaved(false), 3000)
    } catch (err) {
      console.error('Failed to save token:', err)
      setError('Failed to save token to secure storage')
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Authentication Settings</h1>
        <p className="text-gray-400 mt-1">Configure API authentication tokens</p>
      </div>

      <div className="bg-yellow-900/20 border border-yellow-900/50 rounded-lg p-4">
        <div className="flex items-start gap-3">
          <AlertCircle className="h-5 w-5 text-yellow-500 flex-shrink-0 mt-0.5" />
          <div>
            <h3 className="text-sm font-medium text-yellow-300">Security Notice</h3>
            <p className="text-sm text-yellow-400 mt-1">
              Your admin token provides full access to all Titan services. Keep it secure and never share it.
              {remember && ' Token will be stored in your system keychain for convenience.'}
            </p>
          </div>
        </div>
      </div>

      <div className="bg-gray-800 rounded-lg border border-gray-700 p-6">
        <div className="space-y-6">
          {/* Admin Token Input */}
          <div>
            <label htmlFor="admin-token" className="block text-sm font-medium text-gray-300 mb-2">
              Admin Token
            </label>
            <div className="relative">
              <input
                id="admin-token"
                type={showToken ? 'text' : 'password'}
                value={adminToken}
                onChange={(e) => setAdminToken(e.target.value)}
                placeholder="Enter your admin token"
                className={`
                  w-full px-4 py-2 pr-10 bg-gray-700 border rounded-lg
                  text-white placeholder-gray-400
                  focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent
                  ${error ? 'border-red-500' : 'border-gray-600'}
                `}
              />
              <button
                type="button"
                onClick={() => setShowToken(!showToken)}
                className="absolute right-3 top-1/2 transform -translate-y-1/2 text-gray-400 hover:text-white transition-colors"
              >
                {showToken ? <EyeOff className="h-5 w-5" /> : <Eye className="h-5 w-5" />}
              </button>
            </div>
            {error && (
              <p className="mt-2 text-sm text-red-400">{error}</p>
            )}
          </div>

          {/* Remember Token Checkbox */}
          <div className="flex items-center gap-3">
            <input
              id="remember-token"
              type="checkbox"
              checked={remember}
              onChange={(e) => setRemember(e.target.checked)}
              className="h-4 w-4 text-blue-600 bg-gray-700 border-gray-600 rounded focus:ring-blue-500 focus:ring-offset-0"
            />
            <label htmlFor="remember-token" className="text-sm text-gray-300">
              Remember token in system keychain (recommended)
            </label>
          </div>

          {/* Save Button */}
          <div className="flex items-center gap-4">
            <button
              onClick={handleSave}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors flex items-center gap-2"
            >
              <Save className="h-4 w-4" />
              Save Token
            </button>
            {saved && (
              <div className="flex items-center gap-2 text-green-400">
                <CheckCircle className="h-4 w-4" />
                <span className="text-sm">Saved successfully</span>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Token Information */}
      <div className="bg-gray-800 rounded-lg border border-gray-700 p-6">
        <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
          <Shield className="h-5 w-5" />
          Token Information
        </h2>
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-sm text-gray-400">Status</span>
            <span className={`text-sm font-medium ${token ? 'text-green-400' : 'text-red-400'}`}>
              {token ? 'Configured' : 'Not Configured'}
            </span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-sm text-gray-400">Storage</span>
            <span className="text-sm font-medium">
              {remember ? 'System Keychain' : 'Session Only'}
            </span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-sm text-gray-400">Token Prefix</span>
            <span className="text-sm font-mono text-gray-300">
              {token ? `${token.substring(0, 10)}...` : 'N/A'}
            </span>
          </div>
        </div>
      </div>

      {/* Additional Security Tips */}
      <div className="bg-gray-800 rounded-lg border border-gray-700 p-6">
        <h2 className="text-lg font-semibold mb-4">Security Best Practices</h2>
        <ul className="space-y-2 text-sm text-gray-400">
          <li className="flex items-start gap-2">
            <Key className="h-4 w-4 flex-shrink-0 mt-0.5" />
            <span>Use a strong, unique token that's at least 32 characters long</span>
          </li>
          <li className="flex items-start gap-2">
            <Key className="h-4 w-4 flex-shrink-0 mt-0.5" />
            <span>Rotate your token regularly (recommended: every 90 days)</span>
          </li>
          <li className="flex items-start gap-2">
            <Key className="h-4 w-4 flex-shrink-0 mt-0.5" />
            <span>Never commit your token to version control or share it publicly</span>
          </li>
          <li className="flex items-start gap-2">
            <Key className="h-4 w-4 flex-shrink-0 mt-0.5" />
            <span>Enable "Remember token" to avoid typing it repeatedly (uses OS keychain)</span>
          </li>
        </ul>
      </div>
    </div>
  )
}
