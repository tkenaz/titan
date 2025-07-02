"""Test configuration for Memory Service."""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock

from memory_service.config import MemoryConfig
from memory_service.models import ImportanceWeights


@pytest.fixture
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def test_config():
    """Test configuration."""
    return MemoryConfig(
        vector_db={"dsn": "postgresql://test:test@localhost:5432/test"},
        graph_db={"uri": "bolt://localhost:7687", "user": "neo4j", "password": "test"},
        redis={"url": "redis://localhost:6379/15"},
        importance_threshold=0.75,
        gc_threshold=0.25,
        embedding_model="mock-embedding-model"
    )


@pytest.fixture
def mock_embedding_service():
    """Mock embedding service."""
    service = Mock()
    service.create_embedding = AsyncMock(
        return_value=[0.1] * 1536  # Mock embedding
    )
    service.create_embeddings_batch = AsyncMock(
        return_value=[[0.1] * 1536]
    )
    service.cosine_similarity = Mock(return_value=0.85)
    return service


@pytest.fixture
def importance_weights():
    """Test importance weights."""
    return ImportanceWeights()
