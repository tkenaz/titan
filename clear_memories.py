#!/usr/bin/env python3
"""Clear all memories from database for fresh testing."""

import asyncio
import os
from pathlib import Path
import sys

# Add project root to Python path
sys.path.insert(0, str(Path(__file__).parent))

# Disable warnings
os.environ['OTEL_SDK_DISABLED'] = 'true'
os.environ['TOKENIZERS_PARALLELISM'] = 'false'

async def clear_memories():
    """Clear all memories from database."""
    from memory_service.config import MemoryConfig
    from memory_service.storage import VectorStorage, GraphStorage
    from memory_service.embeddings import EmbeddingService
    
    print("🗑️  Clearing all memories...")
    
    # Load config
    config = MemoryConfig.from_yaml('config/memory-local.yaml')
    
    # Connect to storages
    embedding_service = EmbeddingService(config)
    vector_storage = VectorStorage(config, embedding_service)
    graph_storage = GraphStorage(config)
    
    await vector_storage.connect()
    await graph_storage.connect()
    
    try:
        # Clear PostgreSQL
        async with vector_storage._pool.acquire() as conn:
            result = await conn.execute("DELETE FROM memory_entries")
            count = int(result.split()[-1])
            print(f"✅ Deleted {count} memories from PostgreSQL")
        
        # Clear Neo4j
        async with graph_storage._driver.session() as session:
            result = await session.run("MATCH (m:Memory) DETACH DELETE m")
            summary = await result.consume()
            print(f"✅ Deleted {summary.counters.nodes_deleted} nodes from Neo4j")
        
        print("\n🎯 Database is now clean!")
        
    finally:
        await vector_storage.disconnect()
        await graph_storage.disconnect()


if __name__ == "__main__":
    asyncio.run(clear_memories())
