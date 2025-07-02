"""Embeddings generation for memory entries."""

import logging
from typing import List, Optional
import numpy as np

from memory_service.config import MemoryConfig


logger = logging.getLogger(__name__)


class EmbeddingService:
    """Service for generating text embeddings."""
    
    def __init__(self, config: MemoryConfig):
        self.config = config
        self.model_name = config.embedding_model
        self._client = None
        
        # Initialize OpenAI client if API key provided
        if config.openai_api_key:
            try:
                import openai
                self._client = openai.Client(api_key=config.openai_api_key)
                logger.info(f"Initialized OpenAI client with model {self.model_name}")
            except ImportError:
                logger.warning("OpenAI package not installed, using mock embeddings")
    
    async def create_embedding(self, text: str) -> List[float]:
        """Create embedding for text."""
        if self._client:
            try:
                response = self._client.embeddings.create(
                    model=self.model_name,
                    input=text
                )
                return response.data[0].embedding
            except Exception as e:
                logger.error(f"OpenAI embedding failed: {e}")
                return self._create_mock_embedding(text)
        else:
            return self._create_mock_embedding(text)
    
    async def create_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """Create embeddings for multiple texts."""
        if self._client and len(texts) <= 100:  # OpenAI batch limit
            try:
                response = self._client.embeddings.create(
                    model=self.model_name,
                    input=texts
                )
                return [item.embedding for item in response.data]
            except Exception as e:
                logger.error(f"Batch embedding failed: {e}")
        
        # Fallback to individual embeddings
        embeddings = []
        for text in texts:
            embedding = await self.create_embedding(text)
            embeddings.append(embedding)
        return embeddings
    
    def _create_mock_embedding(self, text: str) -> List[float]:
        """Create mock embedding for testing."""
        # Simple hash-based mock embedding
        # In production, use sentence-transformers or similar
        logger.debug(f"Creating mock embedding for text: {text[:50]}...")
        
        # Consistent dimension based on model
        if "small" in self.model_name:
            dim = 1536
        elif "large" in self.model_name:
            dim = 3072
        else:
            dim = 768
        
        # Generate deterministic pseudo-random embedding
        np.random.seed(hash(text) % (2**32))
        embedding = np.random.randn(dim).astype(np.float32)
        
        # Normalize
        embedding = embedding / np.linalg.norm(embedding)
        
        return embedding.tolist()
    
    @staticmethod
    def cosine_similarity(a: List[float], b: List[float]) -> float:
        """Calculate cosine similarity between two embeddings."""
        a_np = np.array(a)
        b_np = np.array(b)
        
        dot_product = np.dot(a_np, b_np)
        norm_a = np.linalg.norm(a_np)
        norm_b = np.linalg.norm(b_np)
        
        if norm_a == 0 or norm_b == 0:
            return 0.0
        
        return float(dot_product / (norm_a * norm_b))
