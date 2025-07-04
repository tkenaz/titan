export interface ElectronAPI {
  // Secure storage
  setSecureValue: (key: string, value: string) => Promise<void>
  getSecureValue: (key: string) => Promise<string | null>
  deleteSecureValue: (key: string) => Promise<void>
  
  // App info
  getVersion: () => Promise<string>
  
  // Platform
  platform: string
}

declare global {
  interface Window {
    electronAPI: ElectronAPI
  }
}
