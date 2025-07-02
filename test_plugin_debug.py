#!/usr/bin/env python3
"""Debug test for plugin execution."""

import asyncio
import json
import logging
from pathlib import Path
import sys

# Enable debug logging
logging.basicConfig(level=logging.DEBUG)

sys.path.insert(0, str(Path(__file__).parent))

from plugin_manager.config import PluginManagerConfig
from plugin_manager.manager import PluginManager


async def debug_test():
    """Test with debug output."""
    print("🔍 Debug Test for Plugin Manager\n")
    
    config = PluginManagerConfig.from_yaml("config/plugins.yaml")
    manager = PluginManager(config)
    
    # Reload plugins first
    await manager.start()
    await manager.reload_plugins()  # Force reload to pick up YAML changes
    
    print(f"Loaded plugins: {list(manager.plugins.keys())}\n")
    
    # Test shell_runner directly
    print("Testing shell_runner with debug...")
    
    event = {
        "event_id": "debug-1",
        "topic": "system.v1",
        "event_type": "run_cmd",
        "timestamp": "2025-01-01T00:00:00Z",
        "payload": {
            "command": "echo 'Hello Titan'"
        }
    }
    
    # Check trigger map
    print(f"Trigger map: {manager.trigger_map}")
    print(f"Event will dispatch to: {manager.trigger_map.get('system.v1:run_cmd', set())}\n")
    
    # Execute directly
    result = await manager.trigger_plugin_manually("shell_runner", event)
    
    print(f"Result:")
    print(f"  Success: {result.success}")
    print(f"  Exit code: {result.exit_code}")
    print(f"  Stdout: {repr(result.stdout)}")
    print(f"  Stderr: {repr(result.stderr)}")
    print(f"  Error: {result.error}")
    print(f"  Duration: {result.duration_ms}ms")
    
    # If failed, let's check the actual Docker command
    if not result.success and result.stderr:
        print(f"\nDocker error details: {result.stderr}")
    
    await manager.stop()


if __name__ == "__main__":
    asyncio.run(debug_test())
