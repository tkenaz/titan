# Titan Desktop

Control center for the Titan autonomous AI system.

## Features

- **Dashboard**: Real-time system monitoring and metrics
- **Memory Explorer**: Search and manage vector memories
- **Plugin Center**: Manage and monitor system plugins
- **Goal Manager**: Schedule and control autonomous goals
- **Model Settings**: Configure AI model preferences
- **Auth Settings**: Secure token management with OS keychain

## Development

```bash
# Install dependencies
npm install

# Start development server
npm run dev

# Build for production
npm run build

# Create distributables
npm run dist
```

## Architecture

- **Frontend**: React 18 + TypeScript + Tailwind CSS
- **State Management**: Redux Toolkit + RTK Query
- **Desktop**: Electron with secure context isolation
- **Real-time**: WebSocket for live event streaming
- **Security**: OS keychain for token storage

## API Integration

The app connects to:
- Memory Service (port 8001)
- Plugin Manager (port 8003)
- Goal Scheduler (port 8004)
- Model Gateway (port 8081)
- WebSocket Bridge (port 8088)

## Production Build

```bash
# Build for all platforms
npm run dist:all

# Build for specific platform
npm run dist  # Current platform only
```

Outputs:
- macOS: `.dmg` file
- Windows: `.exe` installer
- Linux: `.AppImage`
