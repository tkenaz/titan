#!/usr/bin/env python3
"""Test Circuit Breaker and Watchdog functionality."""

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

from plugin_manager.enhanced_manager import EnhancedPluginManager
from plugin_manager.circuit_breaker import PluginState


async def test_circuit_breaker():
    """Test circuit breaker functionality."""
    
    print("\n⚡ CIRCUIT BREAKER TEST")
    print("=" * 50)
    
    # Initialize manager
    manager = EnhancedPluginManager(
        plugin_dir="./plugins",
        redis_url=os.getenv("REDIS_URL", "redis://localhost:6379/0")
    )
    
    await manager.initialize()
    
    try:
        # 1. Test normal execution
        print("\n1️⃣ Testing normal plugin execution...")
        
        # Assuming we have a test plugin
        test_event = {
            "event_type": "test",
            "payload": {"message": "Hello plugin"}
        }
        
        # Get first available plugin
        plugin_names = list(manager.plugins.keys())
        if not plugin_names:
            print("❌ No plugins loaded!")
            return
        
        test_plugin = plugin_names[0]
        print(f"   Using plugin: {test_plugin}")
        
        result = await manager.execute_plugin(test_plugin, test_event)
        print(f"   Result: {result}")
        
        # 2. Test failure handling
        print("\n2️⃣ Testing circuit breaker (simulating failures)...")
        
        # Create a failing event
        failing_event = {
            "event_type": "test",
            "payload": {"force_error": True}  # This should make plugin fail
        }
        
        # Trigger multiple failures
        for i in range(6):
            print(f"   Failure attempt {i+1}/6...")
            result = await manager.execute_plugin(test_plugin, failing_event)
            
            if not result['success']:
                print(f"   ❌ Failed as expected: {result.get('error')}")
                
                # Check health
                health = await manager.circuit_breaker.get_plugin_health(test_plugin)
                print(f"   Health: {health.state.value}, failures: {health.consecutive_failures}")
        
        # 3. Check if plugin is disabled
        print("\n3️⃣ Checking plugin state after failures...")
        
        health = await manager.circuit_breaker.get_plugin_health(test_plugin)
        if health.state == PluginState.DISABLED:
            print(f"   ✅ Plugin correctly DISABLED after {health.consecutive_failures} failures")
            print(f"   Will be re-enabled at: {health.disabled_until}")
        else:
            print(f"   ❓ Plugin state: {health.state.value}")
        
        # Try to execute while disabled
        result = await manager.execute_plugin(test_plugin, test_event)
        if not result['success'] and 'disabled' in result.get('error', '').lower():
            print("   ✅ Plugin correctly rejected while disabled")
        
        # 4. Test manual reset
        print("\n4️⃣ Testing manual reset...")
        
        await manager.reset_plugin(test_plugin)
        health = await manager.circuit_breaker.get_plugin_health(test_plugin)
        
        if health.state == PluginState.ACTIVE:
            print("   ✅ Plugin successfully reset to ACTIVE")
        
        # 5. Test container watchdog
        print("\n5️⃣ Testing container watchdog...")
        
        stats = await manager.watchdog.get_container_stats()
        print(f"   Container stats: {stats}")
        
        # Cleanup any leftover containers
        cleaned = await manager.cleanup_containers()
        print(f"   Cleaned {cleaned} containers")
        
        # 6. Get overall status
        print("\n6️⃣ Overall plugin status...")
        
        status = await manager.get_plugin_status()
        print(f"   Total plugins: {status['total_plugins']}")
        
        for name, info in status['plugins'].items():
            print(f"\n   Plugin: {name}")
            print(f"     State: {info['state']}")
            print(f"     Healthy: {info['healthy']}")
            print(f"     Success rate: {info['success_rate']:.1f}%")
            print(f"     Executions: {info['total_executions']}")
        
    finally:
        await manager.shutdown()
    
    print("\n✅ Circuit breaker test completed!")


async def test_api_auth():
    """Test API authentication."""
    import httpx
    
    print("\n🔐 API AUTHENTICATION TEST")
    print("=" * 50)
    
    # Test endpoints
    memory_url = "http://localhost:8001"
    plugin_url = "http://localhost:8003"
    
    token = os.getenv("ADMIN_TOKEN", "titan-secret-token-change-me-in-production")
    
    async with httpx.AsyncClient() as client:
        # 1. Test without auth
        print("\n1️⃣ Testing without authentication...")
        
        try:
            response = await client.get(f"{memory_url}/memory/stats")
            print(f"   Memory API: {response.status_code} (should be 403)")
        except:
            print("   Memory API not running")
        
        # 2. Test with wrong token
        print("\n2️⃣ Testing with wrong token...")
        
        headers = {"Authorization": "Bearer wrong-token"}
        try:
            response = await client.get(f"{memory_url}/memory/stats", headers=headers)
            print(f"   Memory API: {response.status_code} (should be 401)")
        except:
            print("   Memory API not running")
        
        # 3. Test with correct token
        print("\n3️⃣ Testing with correct token...")
        
        headers = {"Authorization": f"Bearer {token}"}
        try:
            response = await client.get(f"{memory_url}/memory/stats", headers=headers)
            print(f"   Memory API: {response.status_code} (should be 200)")
            if response.status_code == 200:
                print(f"   Stats: {response.json()}")
        except:
            print("   Memory API not running")
        
        # 4. Test health endpoint (no auth)
        print("\n4️⃣ Testing health endpoint (no auth required)...")
        
        try:
            response = await client.get(f"{memory_url}/health")
            print(f"   Health: {response.status_code} - {response.json()}")
        except:
            print("   Memory API not running")


if __name__ == "__main__":
    print("Choose test:")
    print("1. Circuit Breaker")
    print("2. API Authentication")
    print("3. Both")
    
    choice = input("\nEnter choice (1-3): ").strip()
    
    if choice == "1":
        asyncio.run(test_circuit_breaker())
    elif choice == "2":
        asyncio.run(test_api_auth())
    elif choice == "3":
        asyncio.run(test_circuit_breaker())
        asyncio.run(test_api_auth())
    else:
        print("Invalid choice")
