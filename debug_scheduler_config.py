#!/usr/bin/env python3
"""Debug Goal Scheduler Redis connection."""

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from goal_scheduler.config import SchedulerConfig
from titan_bus.config import EventBusConfig, RedisConfig


def test_config():
    """Test configuration loading."""
    
    print("🔍 Testing Goal Scheduler Configuration")
    print("=" * 50)
    
    # Test environment variables
    print("\n1️⃣ Environment Variables:")
    print(f"   SCHEDULER_REDIS_URL: {os.getenv('SCHEDULER_REDIS_URL', 'NOT SET')}")
    print(f"   EVENT_BUS_URL: {os.getenv('EVENT_BUS_URL', 'NOT SET')}")
    
    # Test SchedulerConfig
    print("\n2️⃣ SchedulerConfig:")
    config = SchedulerConfig.from_env()
    print(f"   redis_url: {config.redis_url}")
    print(f"   event_bus_url: {config.event_bus_url}")
    
    # Test RedisConfig creation
    print("\n3️⃣ RedisConfig:")
    redis_config = RedisConfig(url=config.event_bus_url)
    print(f"   url: {redis_config.url}")
    
    # Test EventBusConfig
    print("\n4️⃣ EventBusConfig:")
    bus_config = EventBusConfig(redis=redis_config)
    print(f"   redis.url: {bus_config.redis.url}")
    
    # Test connection
    print("\n5️⃣ Testing Redis connection from container...")
    os.system("docker exec titan-goal-scheduler sh -c 'nc -zv redis-master 6379 || echo Redis not reachable'")
    
    print("\n6️⃣ Checking container network...")
    os.system("docker exec titan-goal-scheduler sh -c 'cat /etc/hosts | grep redis'")


if __name__ == "__main__":
    test_config()
