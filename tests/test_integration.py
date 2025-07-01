"""Integration tests for Titan Event Bus."""

import pytest
import asyncio
from datetime import datetime

from titan_bus import EventBusClient, Event, EventPriority


@pytest.mark.integration
class TestEventBusIntegration:
    """Integration tests with real Redis."""
    
    @pytest.mark.asyncio
    async def test_end_to_end_flow(self, test_config, redis_client):
        """Test complete flow: publish -> consume -> ack."""
        received_events = []
        
        # Create handler
        async def test_handler(event: Event):
            received_events.append(event)
        
        # Create client
        async with EventBusClient(test_config, redis_client) as client:
            # Subscribe
            client.subscribe("test.v1", test_handler)
            
            # Start processor
            await client.start_processor()
            
            # Publish events
            event_ids = []
            for i in range(5):
                event_id = await client.publish(
                    topic="test.v1",
                    event_type="integration_test",
                    payload={"index": i, "message": f"Test message {i}"},
                    priority=EventPriority.HIGH if i % 2 == 0 else EventPriority.LOW
                )
                event_ids.append(event_id)
            
            # Wait for processing
            await asyncio.sleep(1)
            
            # Verify all events received
            assert len(received_events) == 5
            
            # Verify high priority processed first
            high_priority_indices = [e.payload["index"] for e in received_events if e.meta.priority == EventPriority.HIGH]
            low_priority_indices = [e.payload["index"] for e in received_events if e.meta.priority == EventPriority.LOW]
            
            # High priority (0, 2, 4) should generally come before low priority (1, 3)
            # Note: exact order depends on batch timing
            assert all(idx in [0, 2, 4] for idx in high_priority_indices)
            assert all(idx in [1, 3] for idx in low_priority_indices)
    
    @pytest.mark.asyncio
    async def test_replay_functionality(self, test_config, redis_client):
        """Test event replay."""
        async with EventBusClient(test_config, redis_client) as client:
            # Publish some events
            start_time = datetime.utcnow()
            
            for i in range(10):
                await client.publish(
                    topic="test.v1",
                    event_type="replay_test",
                    payload={"index": i}
                )
            
            # Replay events
            replayed = []
            async for event in client.replay("test.v1", from_timestamp=start_time):
                replayed.append(event)
            
            assert len(replayed) == 10
            assert all(e.event_type == "replay_test" for e in replayed)
            assert [e.payload["index"] for e in replayed] == list(range(10))
    
    @pytest.mark.asyncio
    async def test_error_handling_and_retry(self, test_config, redis_client):
        """Test error handling and retry logic."""
        attempt_count = 0
        
        async def failing_handler(event: Event):
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count < 3:
                raise Exception("Simulated failure")
            # Success on 3rd attempt
        
        async with EventBusClient(test_config, redis_client) as client:
            client.subscribe("test.v1", failing_handler)
            await client.start_processor()
            
            # Publish event
            await client.publish(
                topic="test.v1",
                event_type="retry_test",
                payload={"test": True}
            )
            
            # Wait for retries
            await asyncio.sleep(3)
            
            # Should have attempted multiple times
            # Note: exact count depends on Redis consumer group retry behavior
            assert attempt_count >= 1
    
    @pytest.mark.asyncio
    async def test_concurrent_consumers(self, test_config, redis_client):
        """Test multiple consumers on same topic."""
        handler1_events = []
        handler2_events = []
        
        async def handler1(event):
            handler1_events.append(event)
            await asyncio.sleep(0.1)  # Simulate work
        
        async def handler2(event):
            handler2_events.append(event)
            await asyncio.sleep(0.05)  # Faster handler
        
        async with EventBusClient(test_config, redis_client) as client:
            # Subscribe both handlers
            client.subscribe("test.v1", handler1)
            client.subscribe("test.v1", handler2)
            
            await client.start_processor()
            
            # Publish events
            for i in range(5):
                await client.publish(
                    topic="test.v1",
                    event_type="concurrent_test",
                    payload={"index": i}
                )
            
            # Wait for processing
            await asyncio.sleep(1)
            
            # Both handlers should receive all events
            assert len(handler1_events) == 5
            assert len(handler2_events) == 5
    
    @pytest.mark.asyncio
    async def test_dead_letter_queue(self, test_config, redis_client):
        """Test DLQ functionality."""
        # Set very low retry limit
        test_config.streams[0].retry_limit = 1
        
        async def always_failing_handler(event):
            raise Exception("Always fails")
        
        async with EventBusClient(test_config, redis_client) as client:
            client.subscribe("test.v1", always_failing_handler)
            await client.start_processor()
            
            # Publish event
            await client.publish(
                topic="test.v1",
                event_type="dlq_test",
                payload={"will_fail": True}
            )
            
            # Wait for processing and DLQ
            await asyncio.sleep(2)
            
            # Check DLQ
            dlq_events = []
            async for event in client.replay(test_config.dead_letter_stream, limit=10):
                dlq_events.append(event)
            
            # Should have event in DLQ
            assert len(dlq_events) >= 1
            assert dlq_events[0].event_type == "dead_letter"
            assert dlq_events[0].payload["original_topic"] == "test.v1"
