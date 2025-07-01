"""Tests for Event Bus Client."""

import pytest
import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, patch, MagicMock

from titan_bus.client import EventBusClient, publish, subscribe
from titan_bus.event import Event, EventPriority
from titan_bus.exceptions import PublishError


class TestEventBusClient:
    """Test EventBusClient functionality."""
    
    @pytest.mark.asyncio
    async def test_client_connect(self, test_config, mock_redis):
        """Test client connection."""
        client = EventBusClient(test_config, redis_client=mock_redis)
        
        assert not client._connected
        
        await client.connect()
        
        assert client._connected
        assert client._processor is not None
        mock_redis.ping.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_client_disconnect(self, test_config, mock_redis):
        """Test client disconnection."""
        client = EventBusClient(test_config, redis_client=mock_redis)
        
        await client.connect()
        await client.disconnect()
        
        assert not client._connected
        mock_redis.close.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_publish_success(self, test_config, mock_redis):
        """Test successful event publishing."""
        client = EventBusClient(test_config, redis_client=mock_redis)
        await client.connect()
        
        # Mock xadd to return a message ID
        mock_redis.xadd.return_value = b"1234567890-0"
        
        event_id = await client.publish(
            topic="test.v1",
            event_type="test_event",
            payload={"message": "hello"},
            priority=EventPriority.HIGH
        )
        
        assert event_id is not None
        assert len(event_id) == 26  # ULID length
        
        # Verify xadd was called
        mock_redis.xadd.assert_called_once()
        call_args = mock_redis.xadd.call_args
        
        assert call_args[0][0] == "test.v1"  # topic
        assert "data" in call_args[0][1]  # event data
        assert call_args[1]["maxlen"] == 1000  # from test config
    
    @pytest.mark.asyncio
    async def test_publish_not_connected(self, test_config):
        """Test publishing when not connected."""
        client = EventBusClient(test_config)
        
        with pytest.raises(PublishError, match="Client not connected"):
            await client.publish(
                topic="test.v1",
                event_type="test",
                payload={}
            )
    
    @pytest.mark.asyncio
    async def test_publish_error(self, test_config, mock_redis):
        """Test publish error handling."""
        client = EventBusClient(test_config, redis_client=mock_redis)
        await client.connect()
        
        # Mock xadd to raise error
        mock_redis.xadd.side_effect = Exception("Redis error")
        
        with pytest.raises(PublishError, match="Failed to publish event"):
            await client.publish(
                topic="test.v1",
                event_type="test",
                payload={}
            )
    
    def test_subscribe(self, test_config, mock_redis):
        """Test handler subscription."""
        client = EventBusClient(test_config, redis_client=mock_redis)
        
        # Mock processor
        client._processor = MagicMock()
        
        async def handler(event):
            pass
        
        client.subscribe("test.v1", handler)
        
        client._processor.register_handler.assert_called_once_with("test.v1", handler)
    
    def test_subscribe_sync_handler_rejected(self, test_config):
        """Test that sync handlers are rejected."""
        client = EventBusClient(test_config)
        client._processor = MagicMock()
        
        def sync_handler(event):
            pass
        
        # Should raise ValueError via processor
        client._processor.register_handler.side_effect = ValueError("Handler must be async")
        
        with pytest.raises(ValueError, match="Handler must be async"):
            client.subscribe("test.v1", sync_handler)
    
    @pytest.mark.asyncio
    async def test_replay_events(self, test_config, mock_redis):
        """Test event replay functionality."""
        client = EventBusClient(test_config, redis_client=mock_redis)
        await client.connect()
        
        # Mock xrange response
        test_event = Event(
            topic="test.v1",
            event_type="test",
            payload={"msg": "test"}
        )
        
        mock_redis.xrange.return_value = [
            (b"1234567890-0", {b"data": test_event.model_dump_json().encode()})
        ]
        
        # Replay events
        events = []
        async for event in client.replay("test.v1", limit=10):
            events.append(event)
        
        assert len(events) == 1
        assert events[0].event_type == "test"
        assert events[0].payload == {"msg": "test"}
    
    @pytest.mark.asyncio
    async def test_context_manager(self, test_config, mock_redis):
        """Test async context manager."""
        async with EventBusClient(test_config, redis_client=mock_redis) as client:
            assert client._connected
            mock_redis.ping.assert_called_once()
        
        # Should be disconnected after exit
        assert not client._connected
        mock_redis.close.assert_called_once()


class TestGlobalClientFunctions:
    """Test global client convenience functions."""
    
    @pytest.mark.asyncio
    @patch("titan_bus.client._global_client", None)
    async def test_global_publish(self, mock_redis):
        """Test publish using global client."""
        with patch("titan_bus.client.EventBusConfig") as mock_config:
            with patch("titan_bus.client.redis.from_url", return_value=mock_redis):
                mock_redis.xadd.return_value = b"1234567890-0"
                
                event_id = await publish(
                    topic="test.v1",
                    event_type="test",
                    payload={"test": True}
                )
                
                assert event_id is not None
                mock_redis.xadd.assert_called()
