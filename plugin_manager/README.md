# Titan Plugin Manager

Dynamic plugin system for Titan with sandboxed execution.

## 🚀 Quick Start

```bash
# Start all dependencies (Redis, etc)
make up

# Start Plugin Manager
make plugins-up

# List loaded plugins
make plugins-list

# Check health
curl http://localhost:8003/health
```

## 🔌 Built-in Plugins

### file_watcher
Watches for new files and extracts text content.

**Triggers on:**
- `fs.v1` / `file_created` events
- Supports: PDF, Markdown, Text files

**Example:**
```bash
python titan-plugins.py trigger file_watcher -e '{
  "event_id": "test-001",
  "topic": "fs.v1", 
  "event_type": "file_created",
  "payload": {
    "path": "/path/to/document.pdf",
    "mime_type": "application/pdf"
  }
}'
```

### shell_runner
Executes whitelisted shell commands safely.

**Triggers on:**
- `system.v1` / `run_cmd` events

**Allowed commands:**
- ls, df, uname, uptime, date, pwd, whoami, echo

**Example:**
```bash
python titan-plugins.py trigger shell_runner -e '{
  "event_id": "test-002",
  "topic": "system.v1",
  "event_type": "run_cmd", 
  "payload": {
    "command": "uname -a"
  }
}'
```

## 🛡️ Security

All plugins run in Docker containers with:
- No network access (`--network none`)
- Read-only filesystem
- Resource limits (CPU/Memory)
- Dropped capabilities
- Timeout enforcement
- Path-based permissions

## 📝 Creating a Plugin

1. Create directory: `plugins/my_plugin/`

2. Add `plugin.yaml`:
```yaml
name: my_plugin
version: 0.1.0
description: My awesome plugin

triggers:
  - topic: chat.v1
    event_type: user_message

entrypoint: python main.py
image: python:3.12-slim

resources:
  cpu: "100m"
  memory: "256Mi"

permissions:
  fs:
    allow:
      - "/allowed/path/**"
```

3. Add `main.py`:
```python
#!/usr/bin/env python3
import os
import json

event_data = os.environ.get("EVENT_DATA")
event = json.loads(event_data)

# Process event...

result = {
    "event_type": "my_result",
    "topic": "system.v1",
    "payload": {...}
}

print(json.dumps(result))
```

4. Reload plugins:
```bash
make plugins-reload
```

## 🔄 Hot Reload

Plugins can be reloaded without restarting:

```bash
# Via API
curl -X POST http://localhost:8003/plugins/reload

# Via CLI
python titan-plugins.py reload

# Via signal
docker exec titan-plugin-manager kill -HUP 1
```

## 📊 Monitoring

- API: http://localhost:8003
- Metrics: http://localhost:8004/metrics
- Logs: `make plugins-logs`

## 🧪 Testing

```bash
# Test plugin discovery
python test_plugin_manager.py

# Test specific plugin
python titan-plugins.py trigger <plugin_name> -e '<event_json>'

# Check logs
python titan-plugins.py logs <plugin_name>
```

## 🏗️ Architecture

```
Event Bus → Plugin Manager → Sandbox → Plugin
    ↑                           ↓
    └──────── Results ←─────────┘
```

1. Events arrive from Event Bus
2. Plugin Manager matches triggers
3. Tasks queued for execution
4. Sandbox runs plugin in container
5. Results published back to Event Bus

## 🐛 Troubleshooting

**Plugin not loading:**
- Check `plugin.yaml` syntax
- Verify entrypoint exists
- Check logs: `make plugins-logs`

**Plugin failing:**
- Check permissions in `plugin.yaml`
- Verify Docker is running
- Check resource limits

**Can't connect to Docker:**
- Ensure Docker socket is mounted
- Check Docker daemon is running
- Verify permissions on socket

## 📚 API Reference

See http://localhost:8003/docs for interactive API docs.
