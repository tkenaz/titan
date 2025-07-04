import { Menu, app, shell, BrowserWindow } from 'electron'

export function createAppMenu() {
  const isMac = process.platform === 'darwin'

  const template = [
    // App menu (macOS only)
    ...(isMac
      ? [{
          label: app.getName(),
          submenu: [
            { role: 'about' as const },
            { type: 'separator' as const },
            { role: 'services' as const, submenu: [] },
            { type: 'separator' as const },
            { role: 'hide' as const },
            { role: 'hideOthers' as const },
            { role: 'unhide' as const },
            { type: 'separator' as const },
            { role: 'quit' as const }
          ]
        }]
      : []),

    // File menu
    {
      label: 'File',
      submenu: [
        {
          label: 'New Memory',
          accelerator: 'CmdOrCtrl+N',
          click: () => {
            BrowserWindow.getFocusedWindow()?.webContents.send('menu:newMemory')
          }
        },
        { type: 'separator' as const },
        isMac ? { role: 'close' as const } : { role: 'quit' as const }
      ]
    },

    // Edit menu
    {
      label: 'Edit',
      submenu: [
        { role: 'undo' as const },
        { role: 'redo' as const },
        { type: 'separator' as const },
        { role: 'cut' as const },
        { role: 'copy' as const },
        { role: 'paste' as const },
        ...(isMac
          ? [
              { role: 'pasteAndMatchStyle' as const },
              { role: 'delete' as const },
              { role: 'selectAll' as const },
              { type: 'separator' as const },
              {
                label: 'Speech',
                submenu: [
                  { role: 'startSpeaking' as const },
                  { role: 'stopSpeaking' as const }
                ]
              }
            ]
          : [
              { role: 'delete' as const },
              { type: 'separator' as const },
              { role: 'selectAll' as const }
            ])
      ]
    },

    // View menu
    {
      label: 'View',
      submenu: [
        { role: 'reload' as const },
        { role: 'forceReload' as const },
        { role: 'toggleDevTools' as const },
        { type: 'separator' as const },
        { role: 'resetZoom' as const },
        { role: 'zoomIn' as const },
        { role: 'zoomOut' as const },
        { type: 'separator' as const },
        { role: 'togglefullscreen' as const }
      ]
    },

    // Window menu
    {
      label: 'Window',
      submenu: [
        { role: 'minimize' as const },
        { role: 'close' as const },
        ...(isMac
          ? [
              { type: 'separator' as const },
              { role: 'front' as const },
              { type: 'separator' as const },
              { role: 'window' as const }
            ]
          : [])
      ]
    },

    // Help menu
    {
      role: 'help' as const,
      submenu: [
        {
          label: 'Documentation',
          click: async () => {
            await shell.openExternal('https://github.com/titan/desktop')
          }
        },
        {
          label: 'Report Issue',
          click: async () => {
            await shell.openExternal('https://github.com/titan/desktop/issues')
          }
        }
      ]
    }
  ]

  const menu = Menu.buildFromTemplate(template)
  Menu.setApplicationMenu(menu)
}
