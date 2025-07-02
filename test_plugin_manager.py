#!/usr/bin/env python3
"""Test script for Plugin Manager."""

import asyncio
import json
import sys
from pathlib import Path

# Add to path
sys.path.insert(0, str(Path(__file__).parent))

from plugin_manager.config import PluginManagerConfig
from plugin_manager.manager import PluginManager
from plugin_manager.models import PluginTask


async def test_plugin_manager():
    """Test Plugin Manager functionality."""
    print("🧪 Testing Plugin Manager...")
    
    # Load config
    config = PluginManagerConfig.from_yaml("config/plugins.yaml")
    
    # Create manager
    manager = PluginManager(config)
    
    print("\n📦 Starting Plugin Manager...")
    await manager.start()
    
    print(f"\n✅ Loaded plugins: {list(manager.plugins.keys())}")
    
    # Test file_watcher
    print("\n📄 Testing file_watcher plugin...")
    
    test_event = {
        "event_id": "test-001",
        "topic": "fs.v1",
        "event_type": "file_created",
        "timestamp": "2025-01-01T00:00:00Z",
        "payload": {
            "path": "/Users/mvyshhnyvetska/Desktop/titan/README.md",
            "mime_type": "text/markdown"
        }
    }
    
    dispatched = await manager.dispatch_event(test_event)
    print(f"Dispatched to: {dispatched}")
    
    # Wait a bit for processing
    await asyncio.sleep(2)
    
    # Test shell_runner
    print("\n🐚 Testing shell_runner plugin...")
    
    shell_event = {
        "event_id": "test-002", 
        "topic": "system.v1",
        "event_type": "run_cmd",
        "timestamp": "2025-01-01T00:00:01Z",
        "payload": {
            "command": "uname -a"
        }
    }
    
    # Test manual trigger
    result = await manager.trigger_plugin_manually(
        "shell_runner",
        shell_event
    )
    
    print(f"Success: {result.success}")
    print(f"Stdout: {result.stdout}")
    print(f"Duration: {result.duration_ms}ms")
    
    # Get status
    print("\n📊 Plugin Status:")
    status = manager.get_plugin_status()
    print(json.dumps(status, indent=2))
    
    # Test reload
    print("\n🔄 Testing hot reload...")
    await manager.reload_plugins()
    
    # Stop
    await manager.stop()
    print("\n✨ Test complete!")


async def test_dangerous_command():
    """Test that dangerous commands are blocked."""
    print("\n🚫 Testing dangerous command blocking...")
    
    config = PluginManagerConfig.from_yaml("config/plugins.yaml")
    manager = PluginManager(config)
    await manager.start()
    
    dangerous_event = {
        "event_id": "test-danger",
        "topic": "system.v1", 
        "event_type": "run_cmd",
        "timestamp": "2025-01-01T00:00:02Z",
        "payload": {
            "command": "rm -rf /"  # This should be blocked
        }
    }
    
    result = await manager.trigger_plugin_manually(
        "shell_runner",
        dangerous_event
    )
    
    print(f"Success: {result.success}")
    print(f"Error: {result.error or result.stderr}")
    
    await manager.stop()


if __name__ == "__main__":
    asyncio.run(test_plugin_manager())
    # Uncomment to test dangerous commands
    # asyncio.run(test_dangerous_command())
