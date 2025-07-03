#!/usr/bin/env python3
"""Quick test for Memory Service with pgvector fixes."""

import asyncio
import logging
import os
import sys
from pathlib import Path

# Disable OpenTelemetry
os.environ['OTEL_SDK_DISABLED'] = 'true'
os.environ['OTEL_TRACES_EXPORTER'] = 'none'
os.environ['OTEL_METRICS_EXPORTER'] = 'none'
# Disable tokenizers parallelism warning
os.environ['TOKENIZERS_PARALLELISM'] = 'false'

# Add project root to Python path
sys.path.insert(0, str(Path(__file__).parent))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Suppress noisy logs
logging.getLogger('urllib3').setLevel(logging.WARNING)
logging.getLogger('httpx').setLevel(logging.WARNING)
logging.getLogger('opentelemetry').setLevel(logging.ERROR)


async def test_memory_only():
    """Test memory service in isolation."""
    
    print("\n🧠 MEMORY SERVICE TEST")
    print("=" * 50)
    
    # Import after env vars are set
    from memory_service.config import MemoryConfig
    from memory_service.service import MemoryService
    from memory_service.models import EvaluationRequest, SearchRequest
    
    # Initialize with local config
    print("\n1️⃣ Initializing Memory Service...")
    
    # Load config from YAML
    config = MemoryConfig.from_yaml('config/memory-local.yaml')
    service = MemoryService(config)
    
    try:
        await service.connect()
        print("✅ Connected to all backends")
        
        # Test messages
        test_messages = [
            ("Марина обожает кофе с корицей по утрам", "personal"),
            ("Починили pgvector через register_vector в init pool", "technical"), 
            ("Встреча с инвесторами завтра в 14:00", "temporal"),
            ("Планируем запустить MVP через 2 недели", "plans"),
            ("Нет, threshold должен быть 0.65, не 0.3", "correction"),
            ("Привет, как погода?", "casual"),
        ]
        
        print("\n2️⃣ Testing evaluation and storage...")
        saved_count = 0
        
        for message, category in test_messages:
            req = EvaluationRequest(
                message=message,
                source="test",
                context={"category": category}
            )
            
            resp = await service.evaluate_and_save(req)
            status = "✅ SAVED" if resp.saved else "❌ SKIPPED"
            print(f"{status} [{resp.importance_score:.2f}] {category}: {message[:50]}...")
            
            if resp.saved:
                saved_count += 1
        
        print(f"\n📊 Saved {saved_count}/{len(test_messages)} messages")
        
        # Test search
        print("\n3️⃣ Testing vector search...")
        search_queries = [
            "кофе марина утро",
            "pgvector починка", 
            "встреча время",
            "завтра встреча"  # Добавили для проверки
        ]
        
        for query in search_queries:
            req = SearchRequest(query=query, k=3)
            results = await service.search(req)  # Returns list directly
            
            print(f"\n🔍 Query: '{query}'")
            if results:
                for i, result in enumerate(results[:3]):
                    print(f"   {i+1}. [{result.similarity:.3f}] {result.memory.summary[:60]}...")
            else:
                print("   No results found")
        
        # Test duplicate
        print("\n4️⃣ Testing duplicate detection...")
        dup_req = EvaluationRequest(
            message="Марина обожает кофе с корицей по утрам",
            source="test"
        )
        dup_resp = await service.evaluate_and_save(dup_req)
        
        if not dup_resp.saved and "Duplicate" in dup_resp.reason:
            print("✅ Duplicate correctly detected!")
        else:
            print(f"❓ Unexpected result: {dup_resp.reason}")
        
        print("\n✨ All tests completed!")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await service.disconnect()
        print("\n👋 Disconnected")


if __name__ == "__main__":
    asyncio.run(test_memory_only())
