"""Client API for Titan Event Bus."""

import asyncio
import logging
from datetime import datetime
from typing import AsyncGenerator, Callable, Dict, Optional

import redis.asyncio as redis
from opentelemetry import trace
import ulid

from titan_bus.config import EventBusConfig
from titan_bus.event import Event, EventPriority
from titan_bus.exceptions import PublishError
from titan_bus.processor import EventProcessor


logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)

# Global client instance
_global_client: Optional["EventBusClient"] = None


class EventBusClient:
    """Client for interacting with Titan Event Bus."""
    
    def __init__(
        self,
        config: EventBusConfig,
        redis_client: Optional[redis.Redis] = None
    ):
        self.config = config
        self._redis = redis_client
        self._processor: Optional[EventProcessor] = None
        self._connected = False
    
    async def connect(self) -> None:
        """Connect to Redis and initialize processor."""
        if self._connected:
            return
        
        if not self._redis:
            # Prepare connection kwargs
            connection_kwargs = {
                "max_connections": self.config.redis.pool_size,
                "decode_responses": False
            }
            
            # Add password if provided
            if self.config.redis.password:
                connection_kwargs["password"] = self.config.redis.password
                
            self._redis = redis.from_url(
                self.config.redis.url,
                **connection_kwargs
            )
        
        # Test connection
        await self._redis.ping()
        
        # Initialize processor
        self._processor = EventProcessor(self.config, self._redis)
        
        self._connected = True
        logger.info("EventBusClient connected")
    
    async def disconnect(self) -> None:
        """Disconnect from Redis."""
        if not self._connected:
            return
        
        if self._processor and self._processor.running:
            await self._processor.stop()
        
        if self._redis:
            await self._redis.close()
        
        self._connected = False
        logger.info("EventBusClient disconnected")
    
    async def publish(
        self,
        topic: str,
        event_type: str,
        payload: Dict,
        priority: EventPriority = EventPriority.MEDIUM,
        trace_id: Optional[str] = None
    ) -> str:
        """Publish an event to the bus."""
        if not self._connected:
            raise PublishError("Client not connected")
        
        with tracer.start_as_current_span("publish_event") as span:
            # Create event
            event = Event(
                topic=topic,
                event_type=event_type,
                payload=payload,
                meta={
                    "priority": priority,
                    "trace_id": trace_id or str(span.get_span_context().trace_id) if span.get_span_context().trace_id else None,
                    "source": f"titan-bus@{self.config.consumer_group}"
                }
            )
            
            span.set_attributes({
                "event.id": event.event_id,
                "event.topic": topic,
                "event.type": event_type,
                "event.priority": priority.value
            })
            
            try:
                # Get stream config for maxlen
                stream_config = self.config.get_stream_config(topic)
                maxlen = stream_config.maxlen if stream_config else 1_000_000
                
                # Add to stream
                await self._redis.xadd(
                    topic,
                    event.to_redis(),
                    maxlen=maxlen,
                    approximate=True  # Use ~ for better performance
                )
                
                logger.debug(f"Published event {event.event_id} to {topic}")
                return event.event_id
                
            except Exception as e:
                span.record_exception(e)
                raise PublishError(f"Failed to publish event: {e}") from e
    
    def subscribe(self, topic: str, handler: Callable) -> None:
        """Subscribe to a topic with a handler."""
        if not self._processor:
            raise RuntimeError("Client not connected")
        
        self._processor.register_handler(topic, handler)
    
    async def ack(self, topic: str, event_id: str) -> None:
        """Manually acknowledge an event (rarely needed)."""
        if not self._connected:
            raise RuntimeError("Client not connected")
        
        # Convert event_id to message_id if needed
        # This is a simplified version - in production you'd track the mapping
        await self._redis.xack(topic, self.config.consumer_group, event_id.encode())
    
    async def replay(
        self,
        topic: str,
        from_timestamp: Optional[datetime] = None,
        to_timestamp: Optional[datetime] = None,
        limit: int = 1000
    ) -> AsyncGenerator[Event, None]:
        """Replay events from a topic within time range."""
        if not self._connected:
            raise RuntimeError("Client not connected")
        
        # Convert timestamps to Redis IDs
        start_id = f"{int(from_timestamp.timestamp() * 1000)}-0" if from_timestamp else "-"
        end_id = f"{int(to_timestamp.timestamp() * 1000)}-0" if to_timestamp else "+"
        
        # Read events
        count = 0
        while count < limit:
            batch_size = min(100, limit - count)
            events = await self._redis.xrange(
                topic,
                min=start_id,
                max=end_id,
                count=batch_size
            )
            
            if not events:
                break
            
            for msg_id, data in events:
                try:
                    event = Event.from_redis(data)
                    yield event
                    count += 1
                except Exception as e:
                    logger.error(f"Failed to parse event during replay: {e}")
            
            # Update start_id for next batch
            if events:
                start_id = f"({events[-1][0].decode()}"
    
    async def start_processor(self) -> None:
        """Start the event processor."""
        if not self._processor:
            raise RuntimeError("Client not connected")
        
        await self._processor.start()
    
    async def __aenter__(self) -> "EventBusClient":
        """Async context manager entry."""
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.disconnect()


# Convenience functions using global client
async def _get_global_client() -> EventBusClient:
    """Get or create global client."""
    global _global_client
    
    if not _global_client:
        # Load config from environment or default location
        try:
            config = EventBusConfig.from_yaml("/app/config/eventbus.yaml")
        except FileNotFoundError:
            config = EventBusConfig()
        
        _global_client = EventBusClient(config)
        await _global_client.connect()
    
    return _global_client


async def publish(
    topic: str,
    event_type: str,
    payload: Dict,
    priority: EventPriority = EventPriority.MEDIUM
) -> str:
    """Publish an event using global client."""
    client = await _get_global_client()
    return await client.publish(topic, event_type, payload, priority)


def subscribe(topic: str, handler: Callable) -> None:
    """Subscribe to a topic using global client."""
    # This will be called during module initialization, so we defer connection
    async def _subscribe():
        client = await _get_global_client()
        client.subscribe(topic, handler)
    
    # Schedule subscription
    asyncio.create_task(_subscribe())


async def ack(topic: str, event_id: str) -> None:
    """Acknowledge an event using global client."""
    client = await _get_global_client()
    await client.ack(topic, event_id)


async def replay(
    topic: str,
    from_timestamp: Optional[datetime] = None,
    to_timestamp: Optional[datetime] = None,
    limit: int = 1000
) -> AsyncGenerator[Event, None]:
    """Replay events using global client."""
    client = await _get_global_client()
    async for event in client.replay(topic, from_timestamp, to_timestamp, limit):
        yield event
