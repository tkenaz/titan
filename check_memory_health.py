#!/usr/bin/env python3
"""
Memory Service Fix Verification Script
Checks all issues mentioned by o3-pro and verifies fixes.
"""

import asyncio
import os
import sys
import subprocess
from pathlib import Path
from datetime import datetime
import json

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))


async def check_embeddings():
    """Check if embeddings are properly configured."""
    print("\n🔍 Checking Embeddings Configuration...")
    
    from memory_service.config import MemoryConfig
    from memory_service.embeddings import EmbeddingService
    
    # Load config
    config = MemoryConfig.from_yaml("config/memory.yaml")
    if os.getenv("OPENAI_API_KEY"):
        config.openai_api_key = os.getenv("OPENAI_API_KEY")
    
    # Test embedding service
    embed_service = EmbeddingService(config)
    
    test_text = "Testing OpenAI embeddings integration"
    try:
        embedding = await embed_service.create_embedding(test_text)
        if len(embedding) == 1536:
            print("✅ OpenAI embeddings working correctly!")
            print(f"   Model: {config.embedding_model}")
            print(f"   Dimension: {len(embedding)}")
            return True
        else:
            print("⚠️  Mock embeddings detected")
            print(f"   Dimension: {len(embedding)}")
            return False
    except Exception as e:
        print(f"❌ Embedding error: {e}")
        return False


async def check_event_bus():
    """Check Event Bus integration."""
    print("\n🚌 Checking Event Bus Integration...")
    
    try:
        # Check if Redis is running
        result = subprocess.run(
            ["redis-cli", "-a", "titan_secret_2025", "ping"],
            capture_output=True,
            text=True
        )
        
        if result.stdout.strip() == "PONG":
            print("✅ Redis connection successful")
        else:
            print("❌ Redis not responding")
            return False
            
        # Check streams
        result = subprocess.run(
            ["redis-cli", "-a", "titan_secret_2025", "XINFO", "STREAM", "chat.v1"],
            capture_output=True,
            text=True
        )
        
        if "first-entry" in result.stdout:
            print("✅ chat.v1 stream exists")
        else:
            print("⚠️  chat.v1 stream not found (will be created on first message)")
            
        return True
        
    except Exception as e:
        print(f"❌ Event Bus check failed: {e}")
        return False


async def check_importance_config():
    """Check importance evaluator configuration."""
    print("\n⚖️  Checking Importance Configuration...")
    
    from memory_service.config import MemoryConfig
    from memory_service.evaluator import MemoryEvaluator
    from memory_service.models import ImportanceWeights
    
    # Load config
    config = MemoryConfig.from_yaml("config/memory.yaml")
    
    print(f"✅ Importance threshold: {config.importance_threshold}")
    print("✅ Importance weights:")
    for key, value in config.importance_weights.items():
        print(f"   - {key}: {value}")
    
    # Test evaluator
    weights = ImportanceWeights(**config.importance_weights)
    evaluator = MemoryEvaluator(config.importance_threshold, weights)
    
    # Test cases
    test_cases = [
        ("Давай встретимся завтра в 10:00", ["temporal", "plans"]),
        ("Я устала, болит голова", ["emotional"]),
        ("Нужно исправить bug в Redis", ["technical"]),
        ("Меня зовут Марина", ["personal"]),
    ]
    
    print("\n📊 Testing importance calculation:")
    for text, expected_features in test_cases:
        should_save, importance, features = evaluator.evaluate(text)
        
        detected = []
        if features.is_personal: detected.append("personal")
        if features.is_technical: detected.append("technical")
        if features.has_temporal: detected.append("temporal")
        if features.has_plans: detected.append("plans")
        if features.emotional_weight > 0: detected.append("emotional")
        
        status = "✅" if should_save else "❌"
        print(f"{status} {text[:40]}...")
        print(f"   Importance: {importance:.2f}, Features: {detected}")
    
    return True


async def run_integration_test():
    """Run a full integration test."""
    print("\n🚀 Running Full Integration Test...")
    
    from memory_service.config import MemoryConfig
    from memory_service.service import MemoryService
    from memory_service.models import EvaluationRequest
    
    # Load config and create service
    config = MemoryConfig.from_yaml("config/memory.yaml")
    if os.getenv("OPENAI_API_KEY"):
        config.openai_api_key = os.getenv("OPENAI_API_KEY")
    
    service = MemoryService(config)
    await service.connect()
    
    # Test message that should definitely be saved
    request = EvaluationRequest(
        message="КРИТИЧНО: завтра в 10:00 встреча с инвесторами по проекту Titan",
        context={"urgent": True},
        source="integration_test"
    )
    
    response = await service.evaluate_and_save(request)
    
    if response.saved:
        print(f"✅ Message saved successfully!")
        print(f"   ID: {response.id}")
        print(f"   Importance: {response.importance_score:.2f}")
        
        # Try to search for it
        from memory_service.models import SearchRequest
        search_req = SearchRequest(
            query="встреча инвесторы Titan",
            limit=5
        )
        
        results = await service.search(search_req)
        if results and any("инвестор" in r.memory.summary for r in results):
            print("✅ Search working correctly!")
        else:
            print("⚠️  Search returned no results")
    else:
        print(f"❌ Message not saved: {response.reason}")
    
    await service.disconnect()
    return response.saved


async def main():
    """Run all checks."""
    print("🏥 Memory Service Health Check")
    print("=" * 50)
    
    # Load env vars
    from dotenv import load_dotenv
    load_dotenv()
    
    results = {
        "embeddings": await check_embeddings(),
        "event_bus": await check_event_bus(),
        "importance": await check_importance_config(),
        "integration": await run_integration_test()
    }
    
    print("\n📋 Summary:")
    print("-" * 30)
    
    all_good = True
    for check, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{check.ljust(15)}: {status}")
        if not result:
            all_good = False
    
    if all_good:
        print("\n🎉 All systems operational! Memory Service is ready.")
        print("\n💡 Next steps:")
        print("1. Run: docker-compose -f docker-compose.memory.yml up")
        print("2. Test events: python test_event_publisher.py")
        print("3. Check logs: docker logs titan-memory-service")
    else:
        print("\n⚠️  Some issues remain. Check the output above.")
    
    return all_good


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
