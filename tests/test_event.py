"""Tests for Event model."""

import pytest
from datetime import datetime

from titan_bus.event import Event, EventPriority, EventMeta


class TestEventModel:
    """Test Event model functionality."""
    
    def test_event_creation_with_defaults(self):
        """Test creating event with default values."""
        event = Event(
            topic="test.v1",
            event_type="test_event",
            payload={"key": "value"}
        )
        
        assert event.event_id is not None
        assert len(event.event_id) == 26  # ULID length
        assert event.schema_version == 1
        assert event.topic == "test.v1"
        assert event.event_type == "test_event"
        assert event.payload == {"key": "value"}
        assert isinstance(event.timestamp, datetime)
        assert event.meta.priority == EventPriority.MEDIUM
        assert event.meta.retries == 0
    
    def test_event_creation_with_custom_meta(self):
        """Test creating event with custom metadata."""
        meta = EventMeta(
            priority=EventPriority.HIGH,
            retries=2,
            trace_id="trace-123",
            source="test-source"
        )
        
        event = Event(
            topic="test.v1",
            event_type="test_event",
            payload={"key": "value"},
            meta=meta
        )
        
        assert event.meta.priority == EventPriority.HIGH
        assert event.meta.retries == 2
        assert event.meta.trace_id == "trace-123"
        assert event.meta.source == "test-source"
    
    def test_topic_validation(self):
        """Test topic versioning validation."""
        # Valid versioned topic
        event = Event(
            topic="test.v1",
            event_type="test",
            payload={}
        )
        assert event.topic == "test.v1"
        
        # Invalid topic without version
        with pytest.raises(ValueError, match="Topic must be versioned"):
            Event(
                topic="test",
                event_type="test",
                payload={}
            )
        
        # Empty topic
        with pytest.raises(ValueError, match="Topic cannot be empty"):
            Event(
                topic="",
                event_type="test",
                payload={}
            )
    
    def test_payload_size_validation(self):
        """Test payload size limit."""
        # Create large payload (>32KB)
        large_payload = {"data": "x" * 33000}  # >32KB
        
        with pytest.raises(ValueError, match="exceeds 32KB limit"):
            Event(
                topic="test.v1",
                event_type="test",
                payload=large_payload
            )
    
    def test_retry_validation(self):
        """Test retry count validation."""
        with pytest.raises(ValueError, match="Retries cannot be negative"):
            EventMeta(retries=-1)
    
    def test_redis_serialization(self):
        """Test Redis serialization/deserialization."""
        event = Event(
            topic="test.v1",
            event_type="test_event",
            payload={"key": "value", "number": 42}
        )
        
        # Serialize to Redis format
        redis_data = event.to_redis()
        assert "data" in redis_data
        assert isinstance(redis_data["data"], str)
        
        # Deserialize from Redis
        mock_redis_data = {
            b"data": redis_data["data"].encode("utf-8")
        }
        
        restored = Event.from_redis(mock_redis_data)
        assert restored.event_id == event.event_id
        assert restored.topic == event.topic
        assert restored.payload == event.payload
    
    def test_increment_retry(self):
        """Test retry increment functionality."""
        event = Event(
            topic="test.v1",
            event_type="test",
            payload={},
            meta=EventMeta(retries=2)
        )
        
        new_event = event.increment_retry()
        
        # Original unchanged
        assert event.meta.retries == 2
        
        # New event has incremented retry
        assert new_event.meta.retries == 3
        assert new_event.event_id == event.event_id
        assert new_event.payload == event.payload
