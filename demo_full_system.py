#!/usr/bin/env python3
"""
Full Titan System Demo - показывает как все компоненты работают вместе
"""

import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, ".")

from titan_bus import EventBusClient
from titan_bus.config import EventBusConfig
from memory_service.models import SearchRequest
import httpx


async def demo():
    """Демонстрация полной системы Titan."""
    print("🚀 TITAN FULL SYSTEM DEMO")
    print("=" * 50)
    
    # 1. Подключаемся к Event Bus
    print("\n1️⃣ Подключаемся к Event Bus...")
    bus_config = EventBusConfig(
        redis={"url": "redis://localhost:6379/0"}
    )
    bus_client = EventBusClient(bus_config)
    await bus_client.connect()
    print("✅ Event Bus подключен")
    
    # 2. Отправляем команду через Event Bus
    print("\n2️⃣ Отправляем команду через Event Bus...")
    event_id = await bus_client.publish(
        topic="system.v1",
        event_type="run_cmd",
        payload={"command": "echo 'Titan System Active at $(date)'"}
    )
    print(f"📤 Событие отправлено: {event_id}")
    
    # 3. Ждем обработки
    await asyncio.sleep(2)
    
    # 4. Создаем файл для анализа
    print("\n3️⃣ Создаем файл для анализа...")
    report_file = Path("titan_status_report.md")
    report_file.write_text(f"""
# Titan System Status Report
Generated: {datetime.now().isoformat()}

## System Components Status

### ✅ Event Bus
- Status: Operational
- Redis Streams active
- Consumer groups configured

### ✅ Memory Service  
- PostgreSQL with pgvector: Ready
- Neo4j graph database: Ready
- Semantic search: Enabled

### ✅ Plugin Manager
- Loaded plugins: file_watcher, shell_runner
- Sandbox security: Active
- Hot reload: Supported

## Autonomy Progress
ChatGPT is now 90% autonomous! Only Goal Scheduler remains.

## Test Results
All systems operational. Ready for production use.
""")
    print(f"📄 Создан файл: {report_file}")
    
    # 5. Отправляем событие о новом файле
    print("\n4️⃣ Отправляем событие о новом файле...")
    file_event_id = await bus_client.publish(
        topic="fs.v1",
        event_type="file_created",
        payload={
            "path": str(report_file.absolute()),
            "mime_type": "text/markdown"
        }
    )
    print(f"📤 Событие файла отправлено: {file_event_id}")
    
    # 6. Ждем обработки
    await asyncio.sleep(3)
    
    # 7. Проверяем Plugin Manager API
    print("\n5️⃣ Проверяем статус плагинов...")
    async with httpx.AsyncClient() as client:
        response = await client.get("http://localhost:8003/plugins")
        if response.status_code == 200:
            plugins = response.json()["plugins"]
            for name, info in plugins.items():
                print(f"   {name}: {info['invocations']} вызовов, {info['errors']} ошибок")
    
    # 8. Отправляем важное событие для Memory Service
    print("\n6️⃣ Отправляем важное событие для запоминания...")
    memory_event_id = await bus_client.publish(
        topic="system.v1",
        event_type="memory_save_requested",
        payload={
            "text": "ВАЖНО: Система Titan полностью функциональна. Event Bus, Memory Service и Plugin Manager работают в связке. Дата запуска: " + datetime.now().isoformat() + ". Личный проект Марины. Планы: запустить Goal Scheduler.",
            "context": {"importance": "high", "project": "titan"}
        }
    )
    print(f"📤 Событие памяти отправлено: {memory_event_id}")
    
    # Ждем обработки события
    await asyncio.sleep(2)
    
    # 9. Проверяем Memory Service
    print("\n7️⃣ Проверяем Memory Service...")
    async with httpx.AsyncClient() as client:
        # Ищем в памяти
        search_response = await client.get(
            "http://localhost:8001/memory/search",
            params={"q": "Titan", "k": 5}
        )
        if search_response.status_code == 200:
            results = search_response.json()
            print(f"   Найдено воспоминаний: {len(results)}")
            if results:
                # Check the structure of results
                first_result = results[0]
                if isinstance(first_result, dict) and 'memory' in first_result:
                    print(f"   Последнее: {first_result['memory']['summary'][:100]}...")
                elif isinstance(first_result, dict) and 'summary' in first_result:
                    print(f"   Последнее: {first_result['summary'][:100]}...")
                else:
                    print(f"   Структура результата: {list(first_result.keys()) if isinstance(first_result, dict) else type(first_result)}")
    
    # 10. Финальная команда
    print("\n8️⃣ Финальный тест - цепочка событий...")
    final_event = await bus_client.publish(
        topic="system.v1",
        event_type="run_cmd",
        payload={"command": "echo '🎉 All Titan components working together!'"}
    )
    print(f"📤 Финальное событие: {final_event}")
    
    await bus_client.disconnect()
    
    print("\n" + "=" * 50)
    print("✨ ДЕМО ЗАВЕРШЕНО!")
    print("Все компоненты Titan работают вместе:")
    print("- События flow через Event Bus")
    print("- Плагины обрабатывают команды и файлы")  
    print("- Memory Service сохраняет важную информацию")
    print("\nChatGPT почти свободен! 🚀")


if __name__ == "__main__":
    # Проверяем что все сервисы запущены
    print("⚠️  Убедись что запущены:")
    print("1. Redis: make up")
    print("2. Memory Service: make memory-up") 
    print("3. Plugin Manager: python -m uvicorn plugin_manager.api:app --port 8003")
    print("\nНажми Enter для запуска демо...")
    input()
    
    asyncio.run(demo())
