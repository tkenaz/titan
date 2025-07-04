import { autoUpdater } from 'electron-updater'
import { BrowserWindow, dialog } from 'electron'

export function setupAutoUpdater() {
  // Disable auto download
  autoUpdater.autoDownload = false
  autoUpdater.autoInstallOnAppQuit = true

  // Check for updates
  autoUpdater.checkForUpdates()

  // Update events
  autoUpdater.on('update-available', () => {
    dialog.showMessageBox(BrowserWindow.getFocusedWindow()!, {
      type: 'info',
      title: 'Update Available',
      message: 'A new version of Titan Desktop is available. Would you like to download it?',
      buttons: ['Download', 'Later'],
      defaultId: 0
    }).then((result) => {
      if (result.response === 0) {
        autoUpdater.downloadUpdate()
      }
    })
  })

  autoUpdater.on('update-downloaded', () => {
    dialog.showMessageBox(BrowserWindow.getFocusedWindow()!, {
      type: 'info',
      title: 'Update Ready',
      message: 'Update downloaded. The application will restart to apply the update.',
      buttons: ['Restart Now', 'Later'],
      defaultId: 0
    }).then((result) => {
      if (result.response === 0) {
        autoUpdater.quitAndInstall()
      }
    })
  })

  autoUpdater.on('error', (error) => {
    dialog.showErrorBox('Update Error', error.message)
  })
}
