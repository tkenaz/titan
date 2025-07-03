#!/usr/bin/env python3
"""Debug vector search to understand similarity scores."""

import asyncio
import os
from pathlib import Path
import sys

# Add project root to Python path
sys.path.insert(0, str(Path(__file__).parent))

# Disable warnings
os.environ['OTEL_SDK_DISABLED'] = 'true'
os.environ['TOKENIZERS_PARALLELISM'] = 'false'

async def debug_search():
    """Debug why some searches don't find results."""
    from memory_service.config import MemoryConfig
    from memory_service.service import MemoryService
    from memory_service.models import SearchRequest
    
    print("🔍 DEBUG VECTOR SEARCH")
    print("=" * 50)
    
    # Initialize
    config = MemoryConfig.from_yaml('config/memory-local.yaml')
    service = MemoryService(config)
    await service.connect()
    
    try:
        # Test different thresholds
        queries = [
            ("встреча время", [0.7, 0.5, 0.3, 0.1]),
            ("meeting time", [0.5, 0.3]),
            ("14:00", [0.5, 0.3]),
            ("завтра встреча", [0.5, 0.3])
        ]
        
        for query, thresholds in queries:
            print(f"\n📝 Query: '{query}'")
            for threshold in thresholds:
                req = SearchRequest(query=query, k=5, min_similarity=threshold)
                results = await service.search(req)
                
                if results:
                    print(f"  ✅ Threshold {threshold}: Found {len(results)} results")
                    for r in results[:2]:
                        print(f"     [{r.similarity:.3f}] {r.memory.summary[:50]}...")
                else:
                    print(f"  ❌ Threshold {threshold}: No results")
        
        # Also check what's actually in the database
        print("\n📊 All memories in database:")
        req = SearchRequest(query="", k=10, min_similarity=0.0)
        all_results = await service.vector_storage.search(
            await service.embedding_service.create_embedding("test"), 
            k=10, 
            threshold=0.0
        )
        
        for i, r in enumerate(all_results):
            print(f"{i+1}. {r.memory.summary[:60]}...")
            
    finally:
        await service.disconnect()


if __name__ == "__main__":
    asyncio.run(debug_search())
