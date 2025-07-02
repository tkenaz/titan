"""Core Memory Service implementation."""

import asyncio
import logging
from datetime import datetime
from typing import List, Optional, Dict

from memory_service.models import (
    MemoryEntry,
    MemorySearchResult,
    RecentMessage,
    EvaluationRequest,
    EvaluationResponse,
    SearchRequest,
    RememberRequest,
    ForgetRequest,
)
from memory_service.config import MemoryConfig
from memory_service.evaluator import MemoryEvaluator
from memory_service.embeddings import EmbeddingService
from memory_service.storage import VectorStorage, GraphStorage, RecentCache


logger = logging.getLogger(__name__)


class MemoryService:
    """Main memory service coordinating all components."""
    
    def __init__(self, config: MemoryConfig):
        self.config = config
        
        # Initialize components
        self.embedding_service = EmbeddingService(config)
        
        # Create ImportanceWeights from config
        from memory_service.models import ImportanceWeights
        weights = ImportanceWeights(**config.importance_weights)
        self.evaluator = MemoryEvaluator(config.importance_threshold, weights)
        
        # Storage backends
        self.vector_storage = VectorStorage(config, self.embedding_service)
        self.graph_storage = GraphStorage(config)
        self.recent_cache = RecentCache(config)
        
        self._connected = False
    
    async def connect(self):
        """Connect to all storage backends."""
        if self._connected:
            return
        
        await asyncio.gather(
            self.vector_storage.connect(),
            self.graph_storage.connect(),
            self.recent_cache.connect()
        )
        
        self._connected = True
        logger.info("MemoryService connected to all backends")
    
    async def disconnect(self):
        """Disconnect from all storage backends."""
        if not self._connected:
            return
        
        await asyncio.gather(
            self.vector_storage.disconnect(),
            self.graph_storage.disconnect(),
            self.recent_cache.disconnect()
        )
        
        self._connected = False
        logger.info("MemoryService disconnected")
    
    async def evaluate_and_save(
        self,
        request: EvaluationRequest
    ) -> EvaluationResponse:
        """Evaluate message and save if important enough."""
        # Add to recent cache
        recent_msg = RecentMessage(
            id=str(datetime.utcnow().timestamp()),
            text=request.message,
            source=request.source
        )
        await self.recent_cache.add(recent_msg)
        
        # Evaluate importance
        should_save, importance, features = self.evaluator.evaluate(
            request.message,
            request.context
        )
        
        if not should_save:
            return EvaluationResponse(
                saved=False,
                importance_score=importance,
                reason=f"Below threshold ({importance:.2f} < {self.config.importance_threshold})"
            )
        
        # Generate embedding
        embedding = await self.embedding_service.create_embedding(request.message)
        
        # Check for novelty
        if embedding:
            similar = await self.vector_storage.search(
                embedding,
                k=5,
                threshold=0.7
            )
            
            if similar and similar[0].similarity > 0.9:
                # Too similar to existing memory
                await self._update_existing(similar[0].memory.id)
                return EvaluationResponse(
                    saved=False,
                    id=similar[0].memory.id,
                    importance_score=importance,
                    reason=f"Duplicate of {similar[0].memory.id} (similarity: {similar[0].similarity:.2f})"
                )
        
        # Create memory entry
        priority = self.evaluator.determine_priority(importance, features)
        
        memory = MemoryEntry(
            summary=request.message,
            embedding=embedding,
            embedding_model=self.config.embedding_model,
            static_priority=priority,
            tags=features.entities,
            emotional_weight=features.emotional_weight,
            source=request.source,
            metadata={
                "features": features.model_dump(),
                "context": request.context or {},
                "importance_score": importance
            }
        )
        
        # Save to storage
        memory_id = await self.vector_storage.save(memory)
        await self.graph_storage.create_memory_node(memory)
        
        # Update relationships with similar memories
        if embedding and similar:
            related_ids = [r.memory.id for r in similar[:3]]
            await self.graph_storage.update_relationships(
                memory_id,
                related_ids,
                "RELATES_TO"
            )
        
        logger.info(f"Saved new memory {memory_id} with importance {importance:.2f}")
        
        return EvaluationResponse(
            saved=True,
            id=memory_id,
            importance_score=importance,
            reason=f"Saved with priority {priority.value}"
        )
    
    async def search(
        self,
        request: SearchRequest
    ) -> List[MemorySearchResult]:
        """Search for memories."""
        # Generate query embedding
        query_embedding = await self.embedding_service.create_embedding(request.query)
        
        if not query_embedding:
            logger.warning("Failed to generate query embedding")
            return []
        
        # Search vector storage
        results = await self.vector_storage.search(
            query_embedding,
            k=request.k,
            threshold=request.min_similarity
        )
        
        # Filter by tags if specified
        if request.tags:
            results = [
                r for r in results
                if any(tag in r.memory.tags for tag in request.tags)
            ]
        
        # Enhance with graph relationships
        for result in results[:5]:  # Only for top results
            related = await self.graph_storage.find_related(
                result.memory.id,
                max_depth=1
            )
            result.memory.metadata['related'] = related
        
        return results
    
    async def remember(
        self,
        request: RememberRequest
    ) -> str:
        """Explicitly remember something."""
        # Generate embedding
        embedding = await self.embedding_service.create_embedding(request.text)
        
        # Create memory with explicit priority
        memory = MemoryEntry(
            summary=request.text,
            embedding=embedding,
            embedding_model=self.config.embedding_model,
            static_priority=request.priority,
            tags=request.tags or [],
            metadata=request.metadata or {}
        )
        
        # Save
        memory_id = await self.vector_storage.save(memory)
        await self.graph_storage.create_memory_node(memory)
        
        logger.info(f"Explicitly remembered {memory_id}")
        return memory_id
    
    async def forget(
        self,
        request: ForgetRequest
    ) -> bool:
        """Forget a specific memory."""
        # Delete from vector storage
        deleted = await self.vector_storage.delete(request.id)
        
        if deleted:
            # Also remove from graph
            # Note: Neo4j deletion not implemented yet
            logger.info(f"Forgot memory {request.id} (reason: {request.reason})")
        
        return deleted
    
    async def garbage_collect(self) -> List[str]:
        """Run garbage collection to remove old memories."""
        deleted_ids = await self.vector_storage.garbage_collect(
            self.config.gc_threshold
        )
        
        logger.info(f"Garbage collected {len(deleted_ids)} memories")
        return deleted_ids
    
    async def _update_existing(self, memory_id: str):
        """Update usage count for existing memory."""
        memory = await self.vector_storage.get_by_id(memory_id)
        if memory:
            memory.usage_count += 1
            memory.last_accessed = datetime.utcnow()
            await self.vector_storage.save(memory)
