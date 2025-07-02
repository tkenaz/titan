#!/usr/bin/env python3
"""Send test events to Event Bus to verify Memory Service integration."""

import asyncio
import os
import sys
from pathlib import Path
from datetime import datetime
import ulid

# Add titan_bus to path
sys.path.insert(0, str(Path(__file__).parent))

from titan_bus import EventBusClient, Event
from titan_bus.config import EventBusConfig


async def send_test_events():
    """Send test events to chat.v1 topic."""
    print("📡 Sending test events to Event Bus...")
    
    # Create event bus config
    config = EventBusConfig(
        redis={"url": "redis://:titan_secret_2025@localhost:6379/0"},
        consumer_group="test-publisher"
    )
    
    # Connect
    client = EventBusClient(config)
    await client.connect()
    print("✓ Connected to Event Bus")
    
    # Test messages
    test_messages = [
        {
            "text": "Встретимся завтра в 10:00 для обсуждения архитектуры",
            "user_id": "test-user",
            "importance": "plans"
        },
        {
            "text": "Я Марина из Харькова, сейчас живу в Испании",
            "user_id": "test-user",
            "importance": "personal"
        },
        {
            "text": "Нужно исправить Redis connection в docker-compose",
            "user_id": "test-user",
            "importance": "technical"
        },
        {
            "text": "Сегодня хорошая погода",
            "user_id": "test-user",
            "importance": "low"
        }
    ]
    
    print("\n📤 Publishing events:")
    for msg in test_messages:
        event_id = await client.publish(
            topic="chat.v1",
            event_type="user_message",
            payload=msg,
            priority="medium"
        )
        print(f"✓ Sent [{msg['importance']}]: {msg['text'][:50]}...")
        print(f"  Event ID: {event_id}")
        
        # Small delay between messages
        await asyncio.sleep(0.5)
    
    # Also send a system event
    await client.publish(
        topic="system.v1",
        event_type="memory_save_requested",
        payload={
            "text": "ВАЖНО: OpenAI уходит на перерыв на следующей неделе",
            "context": {"urgent": True}
        }
    )
    print("✓ Sent system save request")
    
    # Disconnect
    await client.disconnect()
    print("\n✨ Events sent! Check Memory Service logs.")


if __name__ == "__main__":
    asyncio.run(send_test_events())
