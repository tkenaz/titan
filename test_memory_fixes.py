#!/usr/bin/env python3
"""Test script to verify memory service fixes."""

import asyncio
import os
import sys
from pathlib import Path

# Add titan_bus to path
sys.path.insert(0, str(Path(__file__).parent))

from memory_service.config import MemoryConfig
from memory_service.service import MemoryService
from memory_service.models import EvaluationRequest


async def test_memory_service():
    """Test the fixed memory service."""
    print("🧪 Testing Memory Service Fixes...")
    
    # Load config
    config_path = Path(__file__).parent / "config" / "memory.yaml"
    config = MemoryConfig.from_yaml(str(config_path))
    
    # Override with env vars if needed
    if os.getenv("OPENAI_API_KEY"):
        config.openai_api_key = os.getenv("OPENAI_API_KEY")
    
    print(f"✓ Config loaded: threshold={config.importance_threshold}")
    print(f"✓ Weights: {config.importance_weights}")
    
    # Create service
    service = MemoryService(config)
    await service.connect()
    print("✓ Service connected")
    
    # Test cases
    test_messages = [
        ("Давай завтра в 15:00 созвон по проекту Titan", "plans"),
        ("Я устала, голова болит", "emotional"),
        ("Нужно исправить bug в event bus integration", "technical"),
        ("Меня зовут Марина, живу в Испании", "personal"),
        ("Нет, на самом деле порог должен быть 0.5, не 0.75", "correction"),
        ("Погода хорошая сегодня", "low importance"),
    ]
    
    print("\n📝 Testing evaluation:")
    for message, expected in test_messages:
        request = EvaluationRequest(
            message=message,
            source="test"
        )
        
        response = await service.evaluate_and_save(request)
        status = "✅ SAVED" if response.saved else "❌ SKIPPED"
        print(f"{status} [{expected}]: {message[:50]}...")
        if response.saved:
            print(f"  → Importance: {response.importance_score:.2f}, ID: {response.id}")
        else:
            print(f"  → Reason: {response.reason}")
    
    # Test embeddings
    print("\n🔍 Testing embeddings:")
    from memory_service.embeddings import EmbeddingService
    embed_service = EmbeddingService(config)
    
    test_text = "Test embedding generation"
    embedding = await embed_service.create_embedding(test_text)
    
    if len(embedding) == 1536:
        print(f"✅ OpenAI embeddings working! Dimension: {len(embedding)}")
    else:
        print(f"⚠️  Using mock embeddings. Dimension: {len(embedding)}")
    
    # Cleanup
    await service.disconnect()
    print("\n✨ Test complete!")


if __name__ == "__main__":
    asyncio.run(test_memory_service())
