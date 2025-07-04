import { contextBridge, ipcRenderer } from 'electron'

// Expose protected methods that allow the renderer process to use
// the ipcRenderer without exposing the entire object
contextBridge.exposeInMainWorld('titanAPI', {
  // App info
  getVersion: () => ipcRenderer.invoke('app:getVersion'),
  getPlatform: () => ipcRenderer.invoke('app:getPlatform'),

  // Window controls
  minimizeWindow: () => ipcRenderer.send('window:minimize'),
  maximizeWindow: () => ipcRenderer.send('window:maximize'),
  closeWindow: () => ipcRenderer.send('window:close'),

  // External links
  openExternal: (url: string) => ipcRenderer.send('shell:openExternal', url),

  // Secure storage
  secureStorage: {
    setPassword: (service: string, account: string, password: string) =>
      ipcRenderer.invoke('keytar:setPassword', service, account, password),
    getPassword: (service: string, account: string) =>
      ipcRenderer.invoke('keytar:getPassword', service, account),
    deletePassword: (service: string, account: string) =>
      ipcRenderer.invoke('keytar:deletePassword', service, account),
    findCredentials: (service: string) =>
      ipcRenderer.invoke('keytar:findCredentials', service)
  }
})

// TypeScript types for the exposed API
declare global {
  interface Window {
    titanAPI: {
      getVersion: () => Promise<string>
      getPlatform: () => Promise<NodeJS.Platform>
      minimizeWindow: () => void
      maximizeWindow: () => void
      closeWindow: () => void
      openExternal: (url: string) => void
      secureStorage: {
        setPassword: (service: string, account: string, password: string) => Promise<void>
        getPassword: (service: string, account: string) => Promise<string | null>
        deletePassword: (service: string, account: string) => Promise<boolean>
        findCredentials: (service: string) => Promise<Array<{ account: string; password: string }>>
      }
    }
  }
}
