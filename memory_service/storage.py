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
        # Import pgvector asyncpg support
        import pgvector.asyncpg
        
        self._pool = await asyncpg.create_pool(
            self.config.vector_db.dsn,
            min_size=5,
            max_size=self.config.vector_db.pool_size,
            # Register vector type codec!
            init=pgvector.asyncpg.register_vector
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
                WITH (lists = 100)
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_memory_last_accessed 
                ON memory_entries (last_accessed DESC)
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_memory_tags 
                ON memory_entries USING gin (tags)
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_memory_created 
                ON memory_entries (created_at DESC)
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
                    
                    logger.info(f"Updated existing memory {existing_id}")
                    return existing_id
            
            # pgvector codec handles conversion automatically
            embedding_value = None
            if entry.embedding:
                if hasattr(entry.embedding, 'tolist'):
                    embedding_value = entry.embedding.tolist()
                else:
                    embedding_value = entry.embedding
            
            # Insert new entry
            await conn.execute("""
                INSERT INTO memory_entries (
                    id, summary, embedding, embedding_model, static_priority,
                    usage_count, last_accessed, created_at, tags, 
                    emotional_weight, source, metadata
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
            """,
                entry.id,
                entry.summary,
                embedding_value,  # pgvector codec handles conversion
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
        """Search for similar memories using vector similarity."""
        logger.info(f"VectorStorage.search called with k={k}, threshold={threshold}")
        
        async with self._pool.acquire() as conn:
            # With pgvector codec registered, pass list directly
            if hasattr(query_embedding, 'tolist'):
                embedding_list = query_embedding.tolist()
            else:
                embedding_list = query_embedding
            
            # Vector similarity search - pass list directly, not string!
            rows = await conn.fetch("""
                SELECT 
                    *,
                    1 - (embedding <=> $1) AS similarity
                FROM memory_entries
                WHERE embedding IS NOT NULL
                    AND 1 - (embedding <=> $1) > $2
                ORDER BY similarity DESC
                LIMIT $3
            """, embedding_list, threshold, k)  # Pass list, not string
            
            logger.info(f"Found {len(rows)} similar memories")
            
            search_results = []
            for row in rows:
                try:
                    memory = await self._row_to_memory(row)
                    similarity = float(row['similarity'])
                    logger.debug(f"Memory: {memory.id} (similarity: {similarity:.3f})")
                    search_results.append(
                        MemorySearchResult(
                            memory=memory,
                            similarity=similarity
                        )
                    )
                except Exception as e:
                    logger.error(f"Failed to parse memory row: {e}")
                    continue
            
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
        
        # With pgvector codec, pass list directly
        return await conn.fetch("""
            SELECT 
                *,
                1 - (embedding <=> $1) AS similarity
            FROM memory_entries
            WHERE 1 - (embedding <=> $1) > $2
            ORDER BY embedding <=> $1
            LIMIT $3
        """, embedding_list, threshold, limit)
    
    async def _row_to_memory(self, row: asyncpg.Record) -> MemoryEntry:
        """Convert database row to MemoryEntry."""
        # Parse embedding - now properly handled by pgvector codec
        embedding = row['embedding']  # Will be a list thanks to register_vector
        
        return MemoryEntry(
            id=row['id'],
            summary=row['summary'],
            embedding=embedding,
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
            # Build query with literal depth value
            query = f"""
                MATCH (m:Memory {{id: $id}})-[*1..{max_depth}]-(related:Memory)
                RETURN DISTINCT related.id AS id, related.summary AS summary
                LIMIT 20
            """
            
            result = await session.run(query, id=memory_id)
            
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
