"""Tests for Event Processor."""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from titan_bus.processor import EventProcessor, RateLimiter
from titan_bus.event import Event, EventPriority
from titan_bus.exceptions import ConsumerError


class TestRateLimiter:
    """Test rate limiter functionality."""
    
    def test_rate_limiter_basic(self):
        """Test basic rate limiting."""
        limiter = RateLimiter(rate=10, burst=10)  # 10 per second
        
        # Should allow first 10
        for _ in range(10):
            assert limiter.acquire() is True
        
        # 11th should fail
        assert limiter.acquire() is False
    
    def test_rate_limiter_refill(self):
        """Test token refill over time."""
        limiter = RateLimiter(rate=10, burst=10)
        
        # Exhaust tokens
        for _ in range(10):
            limiter.acquire()
        
        # Mock time passage
        limiter.last_update -= 0.5  # 0.5 seconds ago
        
        # Should have ~5 tokens refilled
        for _ in range(5):
            assert limiter.acquire() is True
        
        assert limiter.acquire() is False


class TestEventProcessor:
    """Test EventProcessor functionality."""
    
    @pytest.mark.asyncio
    async def test_processor_initialization(self, test_config, mock_redis):
        """Test processor initialization."""
        processor = EventProcessor(test_config, mock_redis)
        
        assert processor.config == test_config
        assert processor.redis == mock_redis
        assert not processor.running
        assert len(processor.handlers) == 0
    
    def test_register_handler(self, test_config, mock_redis):
        """Test handler registration."""
        processor = EventProcessor(test_config, mock_redis)
        
        async def handler(event):
            pass
        
        processor.register_handler("test.v1", handler)
        
        assert "test.v1" in processor.handlers
        assert handler in processor.handlers["test.v1"]
    
    def test_register_sync_handler_rejected(self, test_config, mock_redis):
        """Test sync handler rejection."""
        processor = EventProcessor(test_config, mock_redis)
        
        def sync_handler(event):
            pass
        
        with pytest.raises(ValueError, match="Handler must be async"):
            processor.register_handler("test.v1", sync_handler)
    
    @pytest.mark.asyncio
    async def test_start_stop(self, test_config, mock_redis):
        """Test starting and stopping processor."""
        processor = EventProcessor(test_config, mock_redis)
        
        # Mock xgroup_create to avoid BUSYGROUP error
        mock_redis.xgroup_create = AsyncMock()
        mock_redis.xreadgroup = AsyncMock(return_value=[])
        
        await processor.start()
        assert processor.running
        
        # Give tasks time to start
        await asyncio.sleep(0.1)
        
        await processor.stop()
        assert not processor.running
    
    @pytest.mark.asyncio
    async def test_ensure_consumer_group(self, test_config, mock_redis):
        """Test consumer group creation."""
        processor = EventProcessor(test_config, mock_redis)
        
        # First call should create group
        mock_redis.xgroup_create = AsyncMock()
        await processor._ensure_consumer_group("test.v1")
        
        mock_redis.xgroup_create.assert_called_once_with(
            "test.v1",
            test_config.consumer_group,
            id="0",
            mkstream=True
        )
        
        # Second call should skip (already in set)
        mock_redis.xgroup_create.reset_mock()
        await processor._ensure_consumer_group("test.v1")
        mock_redis.xgroup_create.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_process_single_event_success(self, test_config, mock_redis):
        """Test successful event processing."""
        processor = EventProcessor(test_config, mock_redis)
        
        # Register handler
        handler_called = False
        async def handler(event):
            nonlocal handler_called
            handler_called = True
            assert event.event_type == "test"
        
        processor.register_handler("test.v1", handler)
        
        # Create test event
        event = Event(
            topic="test.v1",
            event_type="test",
            payload={"data": "test"}
        )
        
        # Process event
        await processor._process_single_event(
            test_config.streams[0],  # test.v1 config
            "test.v1",
            b"1234567890-0",
            event
        )
        
        assert handler_called
        mock_redis.xack.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_process_single_event_failure(self, test_config, mock_redis):
        """Test event processing failure."""
        processor = EventProcessor(test_config, mock_redis)
        
        # Register failing handler
        async def failing_handler(event):
            raise Exception("Handler error")
        
        processor.register_handler("test.v1", failing_handler)
        
        # Create test event
        event = Event(
            topic="test.v1",
            event_type="test",
            payload={"data": "test"},
            meta={"retries": 0}
        )
        
        # Process event - should not raise
        await processor._process_single_event(
            test_config.streams[0],
            "test.v1",
            b"1234567890-0",
            event
        )
        
        # Should not ACK on failure
        mock_redis.xack.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_process_batch_with_priority(self, test_config, mock_redis):
        """Test batch processing with priority sorting."""
        processor = EventProcessor(test_config, mock_redis)
        
        # Track processing order
        processed_order = []
        
        async def handler(event):
            processed_order.append(event.meta.priority)
        
        processor.register_handler("test.v1", handler)
        
        # Create events with different priorities
        messages = []
        for priority in [EventPriority.LOW, EventPriority.HIGH, EventPriority.MEDIUM]:
            event = Event(
                topic="test.v1",
                event_type="test",
                payload={},
                meta={"priority": priority}
            )
            messages.append((f"{priority}-id".encode(), event.to_redis()))
        
        # Process batch
        await processor._process_batch(
            test_config.streams[0],
            "test.v1",
            messages
        )
        
        # Should process in priority order: HIGH, MEDIUM, LOW
        assert processed_order == [EventPriority.HIGH, EventPriority.MEDIUM, EventPriority.LOW]
    
    @pytest.mark.asyncio
    async def test_send_to_dlq(self, test_config, mock_redis):
        """Test sending event to dead letter queue."""
        processor = EventProcessor(test_config, mock_redis)
        
        event = Event(
            topic="test.v1",
            event_type="test",
            payload={"original": "data"}
        )
        
        await processor._send_to_dlq(
            "test.v1",
            b"1234567890-0",
            event,
            "Test error"
        )
        
        # Should add to DLQ stream
        mock_redis.xadd.assert_called_once()
        call_args = mock_redis.xadd.call_args
        
        assert call_args[0][0] == test_config.dead_letter_stream
        assert "original_topic" in call_args[0][1]["data"]
    
    @pytest.mark.asyncio
    async def test_rate_limiting(self, test_config, mock_redis):
        """Test rate limiting functionality."""
        # Override config with very low rate
        test_config.max_global_rate = 1  # 1 per second
        test_config.streams[0].rate_limit = 1
        
        processor = EventProcessor(test_config, mock_redis)
        
        # Register handler
        process_count = 0
        async def handler(event):
            nonlocal process_count
            process_count += 1
        
        processor.register_handler("test.v1", handler)
        
        # Try to process multiple events quickly
        event = Event(topic="test.v1", event_type="test", payload={})
        
        # First should succeed
        await processor._process_single_event(
            test_config.streams[0],
            "test.v1",
            b"1-0",
            event
        )
        
        # Second should be rate limited (handler not called)
        await processor._process_single_event(
            test_config.streams[0],
            "test.v1",
            b"2-0",
            event
        )
        
        assert process_count == 1  # Only first processed
