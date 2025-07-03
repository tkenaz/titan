#!/usr/bin/env python3
"""Simple test to send event directly to Redis"""

import asyncio
import redis.asyncio as redis
from datetime import datetime
import ulid
import json


async def test_direct():
    # Подключаемся напрямую к Redis
    r = await redis.from_url("redis://localhost:6379/0")
    
    # Создаем событие
    event = {
        "event_id": str(ulid.new()),
        "schema_version": 1,
        "topic": "system.v1",
        "event_type": "run_cmd",
        "timestamp": datetime.utcnow().isoformat(),
        "payload": {
            "command": "echo 'Direct Redis test!'"
        },
        "meta": {
            "priority": "high",
            "source": "test_script"
        }
    }
    
    # Отправляем в стрим
    event_id = await r.xadd(
        "system.v1",
        {"data": json.dumps(event)}
    )
    
    print(f"✅ Event sent directly to Redis: {event_id}")
    
    # Проверяем
    length = await r.xlen("system.v1")
    print(f"📊 Total events in system.v1: {length}")
    
    # Читаем последнее
    messages = await r.xrange("system.v1", "-", "+", count=1)
    if messages:
        print(f"📤 Last event: {messages[-1]}")
    
    await r.close()


if __name__ == "__main__":
    asyncio.run(test_direct())
