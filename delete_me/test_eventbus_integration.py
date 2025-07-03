import asyncio
import sys
sys.path.insert(0, ".")

async def main():
    from titan_bus import EventBusClient
    from titan_bus.config import EventBusConfig
    
    # Подключаемся к Event Bus
    config = EventBusConfig(
        redis={"url": "redis://:titan_secret_2025@localhost:6379/0"}
    )
    client = EventBusClient(config)
    await client.connect()
    
    # Отправляем команду
    print("📤 Sending command via Event Bus...")
    event_id = await client.publish(
        topic="system.v1",
        event_type="run_cmd",
        payload={"command": "echo 'Hello from Event Bus Integration!'"},
        priority="high"
    )
    print(f"✅ Sent event: {event_id}")
    
    # Ждем немного чтобы плагин обработал
    await asyncio.sleep(2)
    
    await client.disconnect()
    print("🔍 Check plugin logs: docker logs titan-plugin-manager")

if __name__ == "__main__":
    asyncio.run(main())
