import { IpcMain } from 'electron'
import * as keytar from 'keytar'

const SERVICE_NAME = 'TitanDesktop'

export function setupSecureStorage(ipcMain: IpcMain) {
  // Store password
  ipcMain.handle('keytar:setPassword', async (_, service: string, account: string, password: string) => {
    try {
      await keytar.setPassword(service || SERVICE_NAME, account, password)
      return true
    } catch (error) {
      console.error('Failed to store password:', error)
      throw error
    }
  })

  // Get password
  ipcMain.handle('keytar:getPassword', async (_, service: string, account: string) => {
    try {
      return await keytar.getPassword(service || SERVICE_NAME, account)
    } catch (error) {
      console.error('Failed to retrieve password:', error)
      return null
    }
  })

  // Delete password
  ipcMain.handle('keytar:deletePassword', async (_, service: string, account: string) => {
    try {
      return await keytar.deletePassword(service || SERVICE_NAME, account)
    } catch (error) {
      console.error('Failed to delete password:', error)
      return false
    }
  })

  // Find all credentials for a service
  ipcMain.handle('keytar:findCredentials', async (_, service: string) => {
    try {
      return await keytar.findCredentials(service || SERVICE_NAME)
    } catch (error) {
      console.error('Failed to find credentials:', error)
      return []
    }
  })
}
