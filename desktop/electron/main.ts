import { app, BrowserWindow, ipcMain, Menu, shell } from 'electron'
import path from 'path'
import { setupSecureStorage } from './secureStorage'
import { createAppMenu } from './menu'
import { setupAutoUpdater } from './autoUpdater'

// Handle creating/removing shortcuts on Windows when installing/uninstalling
if (require('electron-squirrel-startup')) {
  app.quit()
}

let mainWindow: BrowserWindow | null = null
const isDev = process.env.NODE_ENV !== 'production'

// Security: Prevent new window creation
app.on('web-contents-created', (_, contents) => {
  contents.on('new-window', async (event, navigationUrl) => {
    event.preventDefault()
    await shell.openExternal(navigationUrl)
  })
})

// Security: Set Content Security Policy
app.on('ready', () => {
  const { session } = require('electron')
  session.defaultSession.webRequest.onHeadersReceived((details, callback) => {
    callback({
      responseHeaders: {
        ...details.responseHeaders,
        'Content-Security-Policy': [
          "default-src 'self'",
          "script-src 'self' 'unsafe-inline'",
          "style-src 'self' 'unsafe-inline'",
          "img-src 'self' data: https:",
          "connect-src 'self' http://localhost:* ws://localhost:*"
        ].join('; ')
      }
    })
  })
})

function createWindow() {
  // Create the browser window
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 1200,
    minHeight: 700,
    title: 'Titan Desktop',
    icon: path.join(__dirname, '../../assets/icon.png'),
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      sandbox: true,
      preload: path.join(__dirname, 'preload.js')
    },
    backgroundColor: '#0a0a0a',
    titleBarStyle: process.platform === 'darwin' ? 'hiddenInset' : 'default',
    show: false
  })

  // Show window when ready
  mainWindow.once('ready-to-show', () => {
    mainWindow?.show()
  })

  // Load the app
  if (isDev) {
    mainWindow.loadURL('http://localhost:5173')
    mainWindow.webContents.openDevTools()
  } else {
    mainWindow.loadFile(path.join(__dirname, '../renderer/index.html'))
  }

  // Handle window closed
  mainWindow.on('closed', () => {
    mainWindow = null
  })
}

// Setup IPC handlers
function setupIPC() {
  // Secure storage
  setupSecureStorage(ipcMain)

  // App info
  ipcMain.handle('app:getVersion', () => app.getVersion())
  ipcMain.handle('app:getPlatform', () => process.platform)
  
  // Window controls
  ipcMain.on('window:minimize', () => mainWindow?.minimize())
  ipcMain.on('window:maximize', () => {
    if (mainWindow?.isMaximized()) {
      mainWindow.unmaximize()
    } else {
      mainWindow?.maximize()
    }
  })
  ipcMain.on('window:close', () => mainWindow?.close())

  // Open external links
  ipcMain.on('shell:openExternal', (_, url) => {
    shell.openExternal(url)
  })
}

// App event handlers
app.whenReady().then(() => {
  setupIPC()
  createWindow()
  createAppMenu()
  setupAutoUpdater()

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow()
    }
  })
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit()
  }
})

// Security: Prevent remote module
app.on('remote-require', (event) => {
  event.preventDefault()
})

// Security: Limit navigation
app.on('web-contents-created', (_, contents) => {
  contents.on('will-navigate', (event, navigationUrl) => {
    const parsedUrl = new URL(navigationUrl)
    if (parsedUrl.origin !== 'http://localhost:5173' && !navigationUrl.startsWith('file://')) {
      event.preventDefault()
    }
  })
})
