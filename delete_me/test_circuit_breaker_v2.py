#!/usr/bin/env python3
"""Test Circuit Breaker and Watchdog functionality with service checks."""

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


async def check_services():
    """Check if required services are running."""
    import httpx
    
    print("\n🔍 Checking services...")
    services_ok = True
    
    async with httpx.AsyncClient(timeout=2.0) as client:
        # Check Memory Service
        try:
            response = await client.get("http://localhost:8001/health")
            if response.status_code == 200:
                print("   ✅ Memory Service: Running")
            else:
                print("   ❌ Memory Service: Unhealthy")
                services_ok = False
        except:
            print("   ❌ Memory Service: Not running")
            services_ok = False
        
        # Check Plugin Manager
        try:
            response = await client.get("http://localhost:8003/health")
            if response.status_code == 200:
                print("   ✅ Plugin Manager: Running")
            else:
                print("   ❌ Plugin Manager: Unhealthy")
                services_ok = False
        except:
            print("   ❌ Plugin Manager: Not running (optional for circuit breaker test)")
        
        # Check Redis
        redis_ok = False
        try:
            import redis.asyncio as aioredis
            # Try different Redis instances
            redis_instances = [
                ("redis://localhost:6379", "Main"),
                ("redis://localhost:6380", "Replica")
            ]
            
            for url, name in redis_instances:
                try:
                    redis_client = await aioredis.from_url(url, decode_responses=True)
                    await redis_client.ping()
                    await redis_client.close()
                    print(f"   ✅ Redis ({name}): Running on {url}")
                    redis_ok = True
                    break
                except:
                    continue
            
            if not redis_ok:
                print("   ⚠️  Redis: Not accessible from host (but services might use Docker networking)")
                # Don't fail if services are running
                if services_ok:
                    redis_ok = True
        except ImportError:
            print("   ⚠️  Redis: redis.asyncio not installed (pip install redis)")
            # Don't fail the check if services are running
            if services_ok:
                redis_ok = True
        
        if not redis_ok:
            services_ok = False
    
    if not services_ok:
        print("\n⚠️  Some services are not running!")
        print("   Run: ./start_services.sh")
        print("   Or use make commands:")
        print("     make all-up     # Start all services")
        print("     make memory-up  # Start just memory service")
    
    return services_ok


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
    
    async with httpx.AsyncClient(timeout=5.0) as client:
        # First check if services are running
        services_available = True
        
        try:
            await client.get(f"{memory_url}/health")
        except:
            print("⚠️  Memory Service not available - skipping auth tests")
            print("   Run: make memory-up")
            services_available = False
        
        if not services_available:
            return
        
        # 1. Test without auth
        print("\n1️⃣ Testing without authentication...")
        
        try:
            response = await client.get(f"{memory_url}/memory/stats")
            status = response.status_code
            if status == 401:
                print(f"   ✅ Memory API: {status} - Correctly requires auth")
            else:
                print(f"   ❌ Memory API: {status} - Should be 401 Unauthorized")
        except Exception as e:
            print(f"   ❌ Memory API error: {e}")
        
        # 2. Test with wrong token
        print("\n2️⃣ Testing with wrong token...")
        
        headers = {"Authorization": "Bearer wrong-token"}
        try:
            response = await client.get(f"{memory_url}/memory/stats", headers=headers)
            status = response.status_code
            if status == 401:
                print(f"   ✅ Memory API: {status} - Correctly rejects wrong token")
            else:
                print(f"   ❌ Memory API: {status} - Should be 401 Unauthorized")
        except Exception as e:
            print(f"   ❌ Memory API error: {e}")
        
        # 3. Test with correct token
        print("\n3️⃣ Testing with correct token...")
        
        headers = {"Authorization": f"Bearer {token}"}
        try:
            response = await client.get(f"{memory_url}/memory/stats", headers=headers)
            status = response.status_code
            if status == 200:
                print(f"   ✅ Memory API: {status} - Successfully authenticated")
                stats = response.json()
                print(f"   📊 Stats: Total memories: {stats.get('total_memories', 0)}")
            else:
                print(f"   ❌ Memory API: {status} - Should be 200 OK")
                print(f"   Response: {response.text}")
        except Exception as e:
            print(f"   ❌ Memory API error: {e}")
        
        # 4. Test health endpoint (no auth)
        print("\n4️⃣ Testing health endpoint (no auth required)...")
        
        try:
            response = await client.get(f"{memory_url}/health")
            status = response.status_code
            if status == 200:
                print(f"   ✅ Health: {status} - {response.json()}")
            else:
                print(f"   ❌ Health: {status} - Should be 200 OK")
        except Exception as e:
            print(f"   ❌ Health endpoint error: {e}")


async def main():
    """Main test runner."""
    print("🚀 Titan Test Suite")
    print("=" * 50)
    
    # Check services first
    services_ok = await check_services()
    
    if not services_ok:
        print("\n❌ Please start required services before running tests")
        return
    
    print("\nChoose test:")
    print("1. Circuit Breaker")
    print("2. API Authentication") 
    print("3. Both")
    
    choice = input("\nEnter choice (1-3): ").strip()
    
    if choice == "1":
        await test_circuit_breaker()
    elif choice == "2":
        await test_api_auth()
    elif choice == "3":
        await test_circuit_breaker()
        await test_api_auth()
    else:
        print("Invalid choice")


if __name__ == "__main__":
    asyncio.run(main())
