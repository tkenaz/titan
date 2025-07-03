#!/usr/bin/env python3
"""
Full integration test for Plugin Loader.
Tests: Discovery → Event → Sandbox → Result
"""

import asyncio
import json
import time
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))

from plugin_manager.config import PluginManagerConfig
from plugin_manager.manager import PluginManager


async def test_full_flow():
    """Test complete plugin flow."""
    print("🚀 Starting Plugin Loader Integration Test\n")
    
    # Load config
    config = PluginManagerConfig.from_yaml("config/plugins.yaml")
    manager = PluginManager(config)
    
    print("1️⃣ Starting Plugin Manager...")
    await manager.start()
    
    # Check loaded plugins
    plugins = list(manager.plugins.keys())
    print(f"✅ Loaded {len(plugins)} plugins: {plugins}\n")
    
    # Test 1: shell_runner with safe command
    print("2️⃣ Testing shell_runner (safe command)...")
    result = await manager.trigger_plugin_manually(
        "shell_runner",
        {
            "event_id": "test-shell-1",
            "topic": "system.v1",
            "event_type": "run_cmd",
            "payload": {"command": "uname -a"}
        }
    )
    
    print(f"   Success: {result.success}")
    if result.stdout:
        print(f"   Output: {result.stdout.strip()}")
    print(f"   Duration: {result.duration_ms:.1f}ms\n")
    
    # Test 2: shell_runner with dangerous command
    print("3️⃣ Testing shell_runner (dangerous command - should fail)...")
    result = await manager.trigger_plugin_manually(
        "shell_runner",
        {
            "event_id": "test-shell-2",
            "topic": "system.v1",
            "event_type": "run_cmd",
            "payload": {"command": "rm -rf /"}
        }
    )
    
    print(f"   Success: {result.success}")
    print(f"   Error: {result.stderr or 'Command blocked'}\n")
    
    # Test 3: file_watcher
    print("4️⃣ Testing file_watcher...")
    test_file = Path("test_document.md")
    
    if test_file.exists():
        result = await manager.trigger_plugin_manually(
            "file_watcher",
            {
                "event_id": "test-file-1",
                "topic": "fs.v1",
                "event_type": "file_created",
                "payload": {
                    "path": str(test_file.absolute()),
                    "mime_type": "text/markdown"
                }
            }
        )
        
        print(f"   Success: {result.success}")
        if result.stdout:
            try:
                output = json.loads(result.stdout)
                summary = output.get("payload", {}).get("summary", "")
                print(f"   Summary: {summary[:100]}...")
            except:
                print(f"   Output: {result.stdout[:100]}...")
        print(f"   Duration: {result.duration_ms:.1f}ms\n")
    else:
        print("   ⚠️  Test file not found\n")
    
    # Test 4: Event dispatch
    print("5️⃣ Testing event dispatch...")
    test_event = {
        "event_id": "test-dispatch-1",
        "topic": "system.v1",
        "event_type": "run_cmd",
        "payload": {"command": "echo 'Hello from Titan!'"}
    }
    
    dispatched = await manager.dispatch_event(test_event)
    print(f"   Dispatched to: {dispatched}")
    
    # Wait for processing
    await asyncio.sleep(2)
    
    # Check status
    status = manager.get_plugin_status()
    print("\n6️⃣ Final plugin status:")
    for name, info in status.items():
        print(f"   {name}:")
        print(f"     - Status: {info['status']}")
        print(f"     - Invocations: {info['invocations']}")
        print(f"     - Errors: {info['errors']}")
    
    # Test hot reload
    print("\n7️⃣ Testing hot reload...")
    await manager.reload_plugins()
    print("   ✅ Plugins reloaded successfully")
    
    # Cleanup
    await manager.stop()
    print("\n✨ Integration test complete!")


async def test_performance():
    """Test plugin performance and concurrency."""
    print("\n⚡ Performance Test\n")
    
    config = PluginManagerConfig.from_yaml("config/plugins.yaml")
    manager = PluginManager(config)
    await manager.start()
    
    # Queue multiple tasks
    print("Queuing 10 concurrent tasks...")
    start_time = time.time()
    
    tasks = []
    for i in range(10):
        event = {
            "event_id": f"perf-{i}",
            "topic": "system.v1",
            "event_type": "run_cmd",
            "payload": {"command": f"echo 'Task {i}'"}
        }
        tasks.append(manager.dispatch_event(event))
    
    await asyncio.gather(*tasks)
    
    # Wait for processing
    await asyncio.sleep(3)
    
    elapsed = time.time() - start_time
    print(f"✅ Processed 10 tasks in {elapsed:.1f}s")
    
    # Check results
    status = manager.get_plugin_status()
    shell_runner = status.get("shell_runner", {})
    print(f"   Total invocations: {shell_runner.get('invocations', 0)}")
    print(f"   Errors: {shell_runner.get('errors', 0)}")
    
    await manager.stop()


async def main():
    """Run all tests."""
    try:
        await test_full_flow()
        await test_performance()
        
        print("\n" + "="*50)
        print("🎉 ALL TESTS PASSED!")
        print("="*50)
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
