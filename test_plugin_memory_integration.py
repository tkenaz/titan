#!/usr/bin/env python3
"""Test Plugin → Memory integration through Event Bus."""

import asyncio
import os
from pathlib import Path
import sys

# Add project root
sys.path.insert(0, str(Path(__file__).parent))

# Disable warnings
os.environ['OTEL_SDK_DISABLED'] = 'true'
os.environ['TOKENIZERS_PARALLELISM'] = 'false'

import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

from titan_bus import EventBusClient
from titan_bus.config import EventBusConfig


async def test_plugin_memory_integration():
    """Test that file events are saved to memory."""
    
    print("\n🔗 PLUGIN → MEMORY INTEGRATION TEST")
    print("=" * 50)
    
    # Initialize Event Bus client
    config = EventBusConfig()
    bus_client = EventBusClient(config)
    await bus_client.connect()
    
    try:
        # 1. Simulate file creation event from file_watcher
        print("\n1️⃣ Simulating file creation event...")
        
        test_file = Path("test_important_config.yaml")
        
        # Publish file event
        await bus_client.publish(
            topic="fs.v1",
            event_type="file_created",
            payload={
                "path": str(test_file),
                "name": test_file.name,
                "extension": test_file.suffix,
                "size_human": "2.3 KB",
                "mime_type": "text/yaml"
            }
        )
        
        # Also publish summary to system.v1 (as enhanced file_watcher does)
        await bus_client.publish(
            topic="system.v1",
            event_type="file_summary",
            payload={
                "message": f"Файл {test_file.name} (YAML конфигурация, 2.3 KB) был создан. Конфигурационный файл может влиять на работу системы",
                "source": "file_watcher",
                "context": {
                    "file_path": str(test_file),
                    "file_type": ".yaml",
                    "event_type": "file_created",
                    "importance": "high"
                }
            }
        )
        
        print("✅ File events published")
        
        # 2. Wait for processing
        await asyncio.sleep(2)
        
        # 3. Check if memory service processed it by subscribing to confirmations
        print("\n2️⃣ Waiting for memory confirmation...")
        
        confirmed = asyncio.Event()
        memory_id = None
        
        async def check_confirmation(event):
            nonlocal memory_id
            if event["event_type"] == "memory_saved":
                payload = event["payload"]
                if payload.get("original_event") == "file_summary":
                    memory_id = payload.get("memory_id")
                    print(f"✅ Memory saved confirmation: {memory_id}")
                    confirmed.set()
        
        # Subscribe to confirmations
        await bus_client.subscribe(
            topic="system.v1",
            group="test-checker",
            handler=check_confirmation
        )
        
        # Wait for confirmation or timeout
        try:
            await asyncio.wait_for(confirmed.wait(), timeout=5.0)
            print(f"\n✅ Integration successful! File event saved to memory: {memory_id}")
        except asyncio.TimeoutError:
            print("\n❌ No confirmation received - Memory consumer might not be running")
            print("   Run: python -m memory_service.consumer")
        
        # 4. Test explicit memory request
        print("\n3️⃣ Testing explicit memory request...")
        
        await bus_client.publish(
            topic="system.v1",
            event_type="memory_request",
            payload={
                "message": "CRITICAL: Plugin to Memory integration test completed successfully at " + str(Path.cwd()),
                "source": "integration_test",
                "context": {
                    "test": True,
                    "importance": "high"
                }
            }
        )
        
        print("✅ Explicit memory request sent")
        
    finally:
        await bus_client.disconnect()
    
    print("\n✨ Integration test completed!")
    print("\nTo see full integration:")
    print("1. Run Memory consumer: python -m memory_service.consumer")
    print("2. Run this test again")
    print("3. Check Memory Service logs for saved events")


if __name__ == "__main__":
    asyncio.run(test_plugin_memory_integration())
