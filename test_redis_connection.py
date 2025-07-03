#!/usr/bin/env python3
"""Test Redis connection issue."""

import asyncio
import os

# Set ENV vars for test
os.environ["SCHEDULER_REDIS_URL"] = "redis://redis-master:6379/2"
os.environ["EVENT_BUS_URL"] = "redis://redis-master:6379/0"

async def test_connection():
    print("=== Testing Redis Connection Issue ===\n")
    
    # Test 1: Direct Redis connection
    print("1. Direct Redis connection:")
    try:
        import redis.asyncio as aioredis
        r = await aioredis.from_url("redis://redis-master:6379")
        await r.ping()
        print("   ✅ Direct connection works!\n")
    except Exception as e:
        print(f"   ❌ Direct connection failed: {e}\n")
    
    # Test 2: RedisConfig
    print("2. Testing RedisConfig:")
    from titan_bus.config import RedisConfig
    
    # Clear any env vars that might interfere
    for key in list(os.environ.keys()):
        if key.startswith("TITAN_"):
            del os.environ[key]
    
    config1 = RedisConfig(url="redis://redis-master:6379/0")
    print(f"   Created with url param: {config1.url}")
    
    config2 = RedisConfig()
    print(f"   Default config: {config2.url}")
    
    # Test 3: EventBusConfig
    print("\n3. Testing EventBusConfig:")
    from titan_bus.config import EventBusConfig
    
    bus_config = EventBusConfig(redis=config1)
    print(f"   EventBusConfig redis.url: {bus_config.redis.url}")
    
    # Test 4: See what ENV vars RedisConfig might read
    print("\n4. Checking ENV interference:")
    print("   ENV vars that might affect Redis:")
    for key, value in os.environ.items():
        if "REDIS" in key or "TITAN" in key:
            print(f"   {key}={value}")

if __name__ == "__main__":
    asyncio.run(test_connection())
