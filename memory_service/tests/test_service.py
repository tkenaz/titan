"""Tests for Memory Service."""

import pytest
from datetime import datetime, timedelta

from memory_service.models import (
    MemoryEntry,
    StaticPriority,
    EvaluationRequest,
    SearchRequest,
    RememberRequest,
    ForgetRequest,
)
from memory_service.service import MemoryService


class TestMemoryService:
    """Test core memory service functionality."""
    
    @pytest.mark.asyncio
    async def test_evaluate_and_save_new_memory(
        self,
        test_config,
        mock_embedding_service,
        mocker
    ):
        """Test saving a new important memory."""
        # Mock storage
        mock_vector = mocker.Mock()
        mock_vector.connect = mocker.AsyncMock()
        mock_vector.save = mocker.AsyncMock(return_value="mem_123")
        mock_vector.search = mocker.AsyncMock(return_value=[])
        
        mock_graph = mocker.Mock()
        mock_graph.connect = mocker.AsyncMock()
        mock_graph.create_memory_node = mocker.AsyncMock()
        
        mock_cache = mocker.Mock()
        mock_cache.connect = mocker.AsyncMock()
        mock_cache.add = mocker.AsyncMock()
        
        # Create service with mocks
        service = MemoryService(test_config)
        service.embedding_service = mock_embedding_service
        service.vector_storage = mock_vector
        service.graph_storage = mock_graph
        service.recent_cache = mock_cache
        
        await service.connect()
        
        # Test evaluation
        request = EvaluationRequest(
            message="Мой рост 163 см",
            context={"source": "test"}
        )
        
        response = await service.evaluate_and_save(request)
        
        assert response.saved is True
        assert response.id == "mem_123"
        assert response.importance_score > 0.75
        
        # Verify storage calls
        mock_vector.save.assert_called_once()
        mock_graph.create_memory_node.assert_called_once()
        mock_cache.add.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_duplicate_detection(
        self,
        test_config,
        mock_embedding_service,
        mocker
    ):
        """Test detection of duplicate memories."""
        # Mock similar memory found
        similar_memory = mocker.Mock()
        similar_memory.id = "existing_123"
        similar_memory.similarity = 0.95
        similar_memory.memory = MemoryEntry(
            id="existing_123",
            summary="Мой рост 163 см",
            embedding=[0.1] * 1536
        )
        
        mock_vector = mocker.Mock()
        mock_vector.connect = mocker.AsyncMock()
        mock_vector.search = mocker.AsyncMock(return_value=[similar_memory])
        mock_vector.get_by_id = mocker.AsyncMock(return_value=similar_memory.memory)
        mock_vector.save = mocker.AsyncMock()
        
        # Create service
        service = MemoryService(test_config)
        service.embedding_service = mock_embedding_service
        service.vector_storage = mock_vector
        service.graph_storage = mocker.Mock(connect=mocker.AsyncMock())
        service.recent_cache = mocker.Mock(
            connect=mocker.AsyncMock(),
            add=mocker.AsyncMock()
        )
        
        await service.connect()
        
        # Test duplicate
        request = EvaluationRequest(
            message="Мой рост 163 сантиметра"  # Slightly different wording
        )
        
        response = await service.evaluate_and_save(request)
        
        assert response.saved is False
        assert response.id == "existing_123"
        assert "Duplicate" in response.reason
    
    @pytest.mark.asyncio
    async def test_search_memories(
        self,
        test_config,
        mock_embedding_service,
        mocker
    ):
        """Test memory search functionality."""
        # Mock search results
        mock_results = [
            mocker.Mock(
                memory=MemoryEntry(
                    id="mem_1",
                    summary="Рост 163 см",
                    tags=["height", "personal"]
                ),
                similarity=0.89
            ),
            mocker.Mock(
                memory=MemoryEntry(
                    id="mem_2",
                    summary="Вес 55 кг",
                    tags=["weight", "personal"]
                ),
                similarity=0.76
            )
        ]
        
        mock_vector = mocker.Mock()
        mock_vector.connect = mocker.AsyncMock()
        mock_vector.search = mocker.AsyncMock(return_value=mock_results)
        
        mock_graph = mocker.Mock()
        mock_graph.connect = mocker.AsyncMock()
        mock_graph.find_related = mocker.AsyncMock(return_value=[])
        
        # Create service
        service = MemoryService(test_config)
        service.embedding_service = mock_embedding_service
        service.vector_storage = mock_vector
        service.graph_storage = mock_graph
        service.recent_cache = mocker.Mock(connect=mocker.AsyncMock())
        
        await service.connect()
        
        # Test search
        request = SearchRequest(
            query="мой рост",
            k=10,
            tags=["personal"]
        )
        
        results = await service.search(request)
        
        assert len(results) == 2
        assert results[0].memory.id == "mem_1"
        assert results[0].similarity == 0.89
        
        # Verify embedding was created for query
        mock_embedding_service.create_embedding.assert_called_with("мой рост")
    
    @pytest.mark.asyncio
    async def test_garbage_collection(
        self,
        test_config,
        mocker
    ):
        """Test garbage collection of old memories."""
        # Mock GC results
        deleted_ids = ["old_1", "old_2", "old_3"]
        
        mock_vector = mocker.Mock()
        mock_vector.connect = mocker.AsyncMock()
        mock_vector.garbage_collect = mocker.AsyncMock(return_value=deleted_ids)
        
        # Create service
        service = MemoryService(test_config)
        service.vector_storage = mock_vector
        service.graph_storage = mocker.Mock(connect=mocker.AsyncMock())
        service.recent_cache = mocker.Mock(connect=mocker.AsyncMock())
        
        await service.connect()
        
        # Run GC
        result = await service.garbage_collect()
        
        assert result == deleted_ids
        mock_vector.garbage_collect.assert_called_once_with(test_config.gc_threshold)


class TestMemoryEntry:
    """Test memory entry model."""
    
    def test_decay_score_calculation(self):
        """Test decay score for GC."""
        memory = MemoryEntry(
            summary="Test memory",
            usage_count=10,
            emotional_weight=0.5
        )
        
        # Fresh memory
        score = memory.calculate_decay_score(days_old=0)
        assert score == 10.5  # usage_count + emotional_weight
        
        # Old memory
        score = memory.calculate_decay_score(days_old=30)
        assert score < 1.0  # Should decay significantly
    
    def test_embedding_validation(self):
        """Test embedding dimension validation."""
        # Valid embedding
        memory = MemoryEntry(
            summary="Test",
            embedding=[0.1] * 1536  # Valid OpenAI dimension
        )
        assert len(memory.embedding) == 1536
        
        # Invalid embedding dimension
        with pytest.raises(ValueError):
            MemoryEntry(
                summary="Test",
                embedding=[0.1] * 100  # Invalid dimension
            )
