"""Storage backends for Memory Service."""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Tuple
import json

import asyncpg
import redis.asyncio as redis
from neo4j import AsyncGraphDatabase
import numpy as np

from memory_service.models import (
    MemoryEntry,
    MemorySearchResult,
    RecentMessage,
    StaticPriority,
)
from memory_service.config import MemoryConfig
from memory_service.embeddings import EmbeddingService


logger = logging.getLogger(__name__)


class VectorStorage:
    """PostgreSQL + pgvector storage for embeddings."""
    
    def __init__(self, config: MemoryConfig, embedding_service: EmbeddingService):
        self.config = config
        self.embedding_service = embedding_service
        self._pool: Optional[asyncpg.Pool] = None
    
    async def connect(self):
        """Initialize connection pool."""
        self._pool = await asyncpg.create_pool(
            self.config.vector_db.dsn,
            min_size=5,
            max_size=self.config.vector_db.pool_size
        )
        
        # Ensure pgvector extension and table exist
        async with self._pool.acquire() as conn:
            await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS memory_entries (
                    id TEXT PRIMARY KEY,
                    summary TEXT NOT NULL,
                    embedding vector(1536),
                    embedding_model TEXT NOT NULL,
                    static_priority TEXT NOT NULL,
                    usage_count INTEGER DEFAULT 1,
                    last_accessed TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    tags JSONB DEFAULT '[]'::jsonb,
                    emotional_weight FLOAT DEFAULT 0.0,
                    source TEXT,
                    metadata JSONB DEFAULT '{}'::jsonb
                )
            """)
            
            # Create indexes
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_memory_embedding 
                ON memory_entries USING ivfflat (embedding vector_cosine_ops)
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_memory_last_accessed 
                ON memory_entries (last_accessed DESC)
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_memory_tags 
                ON memory_entries USING gin (tags)
            """)
        
        logger.info("VectorStorage connected and initialized")
    
    async def disconnect(self):
        """Close connection pool."""
        if self._pool:
            await self._pool.close()
    
    async def save(self, entry: MemoryEntry) -> str:
        """Save memory entry to vector store."""
        async with self._pool.acquire() as conn:
            # Check for duplicates
            if entry.embedding:
                similar = await self._find_similar(
                    conn,
                    entry.embedding,
                    threshold=0.9,
                    limit=1
                )
                
                if similar:
                    # Update existing entry
                    existing_id = similar[0][0]
                    await conn.execute("""
                        UPDATE memory_entries 
                        SET usage_count = usage_count + 1,
                            last_accessed = CURRENT_TIMESTAMP
                        WHERE id = $1
                    """, existing_id)
                    
                    logger.info(f"Updated existing memory {existing_id} (similarity: {similar[0][1]:.3f})")
                    return existing_id
            
            # Convert embedding to PostgreSQL vector format
            embedding_str = None
            if entry.embedding:
                if hasattr(entry.embedding, 'tolist'):
                    embedding_list = entry.embedding.tolist()
                else:
                    embedding_list = entry.embedding
                embedding_str = '[' + ','.join(map(str, embedding_list)) + ']'
            
            # Insert new entry
            await conn.execute("""
                INSERT INTO memory_entries (
                    id, summary, embedding, embedding_model, static_priority,
                    usage_count, last_accessed, created_at, tags, 
                    emotional_weight, source, metadata
                ) VALUES ($1, $2, $3::vector, $4, $5, $6, $7, $8, $9, $10, $11, $12)
            """,
                entry.id,
                entry.summary,
                embedding_str,
                entry.embedding_model,
                entry.static_priority.value,
                entry.usage_count,
                entry.last_accessed,
                entry.created_at,
                json.dumps(entry.tags),
                entry.emotional_weight,
                entry.source,
                json.dumps(entry.metadata)
            )
            
            logger.info(f"Saved new memory {entry.id}")
            return entry.id
    
    async def search(
        self,
        query_embedding: List[float],
        k: int = 10,
        threshold: float = 0.5
    ) -> List[MemorySearchResult]:
        """Search for similar memories."""
        async with self._pool.acquire() as conn:
            results = await self._find_similar(conn, query_embedding, threshold, k)
            
            search_results = []
            for row in results:
                memory = await self._row_to_memory(row)
                search_results.append(
                    MemorySearchResult(
                        memory=memory,
                        similarity=row['similarity']
                    )
                )
            
            return search_results
    
    async def get_by_id(self, memory_id: str) -> Optional[MemoryEntry]:
        """Get memory by ID."""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM memory_entries WHERE id = $1",
                memory_id
            )
            
            if row:
                # Update access time
                await conn.execute(
                    "UPDATE memory_entries SET last_accessed = CURRENT_TIMESTAMP WHERE id = $1",
                    memory_id
                )
                return await self._row_to_memory(row)
            
            return None
    
    async def delete(self, memory_id: str) -> bool:
        """Delete memory entry."""
        async with self._pool.acquire() as conn:
            result = await conn.execute(
                "DELETE FROM memory_entries WHERE id = $1",
                memory_id
            )
            return result.split()[-1] == "1"
    
    async def garbage_collect(self, threshold: float = 0.25) -> List[str]:
        """Remove old memories with low scores."""
        async with self._pool.acquire() as conn:
            # Calculate decay scores and delete low-scoring entries
            deleted_ids = await conn.fetch("""
                WITH scored_memories AS (
                    SELECT 
                        id,
                        usage_count / (1.0 + EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - last_accessed)) / 86400) 
                        + emotional_weight AS score,
                        static_priority
                    FROM memory_entries
                    WHERE static_priority != 'high'
                )
                DELETE FROM memory_entries
                WHERE id IN (
                    SELECT id FROM scored_memories WHERE score < $1
                )
                RETURNING id
            """, threshold)
            
            return [row['id'] for row in deleted_ids]
    
    async def _find_similar(
        self,
        conn: asyncpg.Connection,
        embedding: List[float],
        threshold: float,
        limit: int
    ) -> List[asyncpg.Record]:
        """Find similar entries using vector similarity."""
        # Convert to list if numpy array
        if hasattr(embedding, 'tolist'):
            embedding_list = embedding.tolist()
        else:
            embedding_list = embedding
            
        # Convert to PostgreSQL vector format
        vector_str = '[' + ','.join(map(str, embedding_list)) + ']'
        
        return await conn.fetch("""
            SELECT 
                *,
                1 - (embedding <=> $1::vector) AS similarity
            FROM memory_entries
            WHERE 1 - (embedding <=> $1::vector) > $2
            ORDER BY embedding <=> $1::vector
            LIMIT $3
        """, vector_str, threshold, limit)
    
    async def _row_to_memory(self, row: asyncpg.Record) -> MemoryEntry:
        """Convert database row to MemoryEntry."""
        return MemoryEntry(
            id=row['id'],
            summary=row['summary'],
            embedding=row['embedding'].tolist() if row['embedding'] else None,
            embedding_model=row['embedding_model'],
            static_priority=StaticPriority(row['static_priority']),
            usage_count=row['usage_count'],
            last_accessed=row['last_accessed'],
            created_at=row['created_at'],
            tags=json.loads(row['tags']) if row['tags'] else [],
            emotional_weight=row['emotional_weight'],
            source=row['source'],
            metadata=json.loads(row['metadata']) if row['metadata'] else {}
        )


class GraphStorage:
    """Neo4j storage for relationships between memories."""
    
    def __init__(self, config: MemoryConfig):
        self.config = config
        self._driver = None
    
    async def connect(self):
        """Initialize Neo4j driver."""
        self._driver = AsyncGraphDatabase.driver(
            self.config.graph_db.uri,
            auth=(self.config.graph_db.user, self.config.graph_db.password)
        )
        
        # Create constraints
        async with self._driver.session() as session:
            await session.run(
                "CREATE CONSTRAINT IF NOT EXISTS FOR (m:Memory) REQUIRE m.id IS UNIQUE"
            )
            await session.run(
                "CREATE CONSTRAINT IF NOT EXISTS FOR (p:Person) REQUIRE p.name IS UNIQUE"
            )
            await session.run(
                "CREATE CONSTRAINT IF NOT EXISTS FOR (c:Concept) REQUIRE c.name IS UNIQUE"
            )
        
        logger.info("GraphStorage connected and initialized")
    
    async def disconnect(self):
        """Close Neo4j driver."""
        if self._driver:
            await self._driver.close()
    
    async def create_memory_node(self, memory: MemoryEntry):
        """Create memory node in graph."""
        async with self._driver.session() as session:
            await session.run("""
                MERGE (m:Memory {id: $id})
                SET m.summary = $summary,
                    m.created_at = $created_at,
                    m.tags = $tags
            """,
                id=memory.id,
                summary=memory.summary,
                created_at=memory.created_at.isoformat(),
                tags=memory.tags
            )
            
            # Create entity nodes and relationships
            for entity in memory.metadata.get('entities', []):
                await self._create_entity_relationship(session, memory.id, entity)
    
    async def update_relationships(
        self,
        memory_id: str,
        related_memory_ids: List[str],
        relationship_type: str = "RELATES_TO"
    ):
        """Update relationships between memories."""
        async with self._driver.session() as session:
            for related_id in related_memory_ids:
                await session.run(f"""
                    MATCH (m1:Memory {{id: $from_id}}), (m2:Memory {{id: $to_id}})
                    MERGE (m1)-[r:{relationship_type}]->(m2)
                    SET r.created_at = datetime()
                """,
                    from_id=memory_id,
                    to_id=related_id
                )
    
    async def find_related(
        self,
        memory_id: str,
        max_depth: int = 2
    ) -> List[Dict]:
        """Find memories related to given memory."""
        async with self._driver.session() as session:
            result = await session.run("""
                MATCH (m:Memory {id: $id})-[*1..$depth]-(related:Memory)
                RETURN DISTINCT related.id AS id, related.summary AS summary
                LIMIT 20
            """,
                id=memory_id,
                depth=max_depth
            )
            
            return [dict(record) async for record in result]
    
    async def _create_entity_relationship(
        self,
        session,
        memory_id: str,
        entity: str
    ):
        """Create relationship between memory and entity."""
        # Simple entity type detection
        if '@' in entity:
            node_type = "Email"
        elif entity[0].isupper():
            node_type = "Person"
        else:
            node_type = "Concept"
        
        await session.run(f"""
            MATCH (m:Memory {{id: $memory_id}})
            MERGE (e:{node_type} {{name: $entity}})
            MERGE (m)-[:MENTIONS]->(e)
        """,
            memory_id=memory_id,
            entity=entity
        )


class RecentCache:
    """Redis cache for recent messages."""
    
    def __init__(self, config: MemoryConfig):
        self.config = config
        self._redis: Optional[redis.Redis] = None
        self.key_prefix = "memory:recent:"
    
    async def connect(self):
        """Initialize Redis connection."""
        self._redis = redis.from_url(self.config.redis.url)
        await self._redis.ping()
        logger.info("RecentCache connected")
    
    async def disconnect(self):
        """Close Redis connection."""
        if self._redis:
            await self._redis.close()
    
    async def add(self, message: RecentMessage):
        """Add message to recent cache."""
        key = f"{self.key_prefix}messages"
        
        # Add to sorted set with timestamp as score
        await self._redis.zadd(
            key,
            {message.model_dump_json(): message.timestamp.timestamp()}
        )
        
        # Trim to max size
        await self._redis.zremrangebyrank(key, 0, -self.config.redis.max_recent - 1)
        
        # Set TTL
        await self._redis.expire(key, self.config.redis.ttl_hours * 3600)
    
    async def get_recent(self, count: int = 50) -> List[RecentMessage]:
        """Get recent messages."""
        key = f"{self.key_prefix}messages"
        
        # Get most recent messages
        messages = await self._redis.zrevrange(key, 0, count - 1)
        
        return [
            RecentMessage.model_validate_json(msg)
            for msg in messages
        ]
    
    async def search_context(
        self,
        query: str,
        window_minutes: int = 30
    ) -> List[RecentMessage]:
        """Search recent messages for context."""
        recent = await self.get_recent(self.config.redis.max_recent)
        
        # Filter by time window
        cutoff = datetime.utcnow() - timedelta(minutes=window_minutes)
        recent = [msg for msg in recent if msg.timestamp > cutoff]
        
        # Simple text search (in production, use Redis search)
        query_lower = query.lower()
        relevant = [
            msg for msg in recent
            if query_lower in msg.text.lower()
        ]
        
        return relevant
