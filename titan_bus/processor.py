"""Event processor - the heart of Titan Event Bus."""

import asyncio
import logging
import time
from collections import defaultdict
from datetime import datetime
from typing import Callable, Dict, List, Optional, Set, Tuple

import redis.asyncio as redis
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode
from prometheus_client import Counter, Histogram, Gauge

from titan_bus.config import EventBusConfig, StreamConfig
from titan_bus.event import Event, EventPriority
from titan_bus.exceptions import ConsumerError, DeadLetterError, RateLimitError


logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)

# Prometheus metrics
messages_processed = Counter(
    "titan_bus_messages_processed_total",
    "Total messages processed",
    ["topic", "status"]
)
processing_duration = Histogram(
    "titan_bus_processing_duration_seconds",
    "Message processing duration",
    ["topic"]
)
active_consumers = Gauge(
    "titan_bus_active_consumers",
    "Number of active consumers",
    ["topic"]
)
dlq_messages = Counter(
    "titan_bus_dlq_messages_total",
    "Messages sent to dead letter queue",
    ["topic", "reason"]
)


class RateLimiter:
    """Token bucket rate limiter."""
    
    def __init__(self, rate: int, burst: int = None):
        self.rate = rate
        self.burst = burst or rate
        self.tokens = self.burst
        self.last_update = time.monotonic()
    
    def acquire(self, count: int = 1) -> bool:
        """Try to acquire tokens."""
        now = time.monotonic()
        elapsed = now - self.last_update
        
        # Refill tokens
        self.tokens = min(self.burst, self.tokens + elapsed * self.rate)
        self.last_update = now
        
        if self.tokens >= count:
            self.tokens -= count
            return True
        return False


class EventProcessor:
    """Main event processor coordinating all consumers."""
    
    def __init__(self, config: EventBusConfig, redis_client: redis.Redis):
        self.config = config
        self.redis = redis_client
        self.handlers: Dict[str, List[Callable]] = defaultdict(list)
        self.running = False
        self._tasks: Set[asyncio.Task] = set()
        
        # Rate limiters
        self.global_limiter = RateLimiter(config.max_global_rate)
        self.topic_limiters: Dict[str, RateLimiter] = {}
        
        # Priority queue for batch sorting
        self.priority_weights = config.priority_weights
        
        # Initialize consumer groups
        self._initialized_groups: Set[str] = set()
    
    def register_handler(self, topic: str, handler: Callable) -> None:
        """Register a handler for a topic."""
        if not asyncio.iscoroutinefunction(handler):
            raise ValueError(f"Handler {handler.__name__} must be async")
        self.handlers[topic].append(handler)
        logger.info(f"Registered handler {handler.__name__} for topic {topic}")
    
    async def start(self) -> None:
        """Start the event processor."""
        if self.running:
            return
        
        self.running = True
        logger.info("Starting Event Processor")
        
        # Create consumer tasks for each configured stream
        for stream_config in self.config.streams:
            task = asyncio.create_task(self._consume_stream(stream_config))
            self._tasks.add(task)
            task.add_done_callback(self._tasks.discard)
        
        # Start metrics server
        asyncio.create_task(self._run_metrics_server())
    
    async def stop(self) -> None:
        """Stop the event processor."""
        logger.info("Stopping Event Processor")
        self.running = False
        
        # Cancel all tasks
        for task in self._tasks:
            task.cancel()
        
        # Wait for cancellation
        await asyncio.gather(*self._tasks, return_exceptions=True)
    
    async def _ensure_consumer_group(self, stream: str) -> None:
        """Ensure consumer group exists."""
        if stream in self._initialized_groups:
            return
        
        try:
            await self.redis.xgroup_create(
                stream, 
                self.config.consumer_group,
                id="0",
                mkstream=True
            )
            self._initialized_groups.add(stream)
            logger.info(f"Created consumer group {self.config.consumer_group} for {stream}")
        except redis.ResponseError as e:
            if "BUSYGROUP" not in str(e):
                raise
            self._initialized_groups.add(stream)
    
    async def _consume_stream(self, stream_config: StreamConfig) -> None:
        """Consume events from a single stream."""
        topic = stream_config.name
        
        # Initialize rate limiter for this topic
        self.topic_limiters[topic] = RateLimiter(stream_config.rate_limit)
        
        # Ensure consumer group exists
        await self._ensure_consumer_group(topic)
        
        active_consumers.labels(topic=topic).inc()
        try:
            while self.running:
                try:
                    # Read batch of messages
                    messages = await self.redis.xreadgroup(
                        self.config.consumer_group,
                        f"consumer-{topic}",
                        {topic: ">"},
                        count=self.config.batch_size,
                        block=self.config.block_timeout
                    )
                    
                    if not messages:
                        continue
                    
                    # Process batch
                    for stream_name, stream_messages in messages:
                        await self._process_batch(
                            stream_config,
                            stream_name.decode(),
                            stream_messages
                        )
                        
                except Exception as e:
                    logger.error(f"Error consuming from {topic}: {e}", exc_info=True)
                    await asyncio.sleep(1)
        finally:
            active_consumers.labels(topic=topic).dec()
    
    async def _process_batch(
        self, 
        stream_config: StreamConfig,
        topic: str,
        messages: List[Tuple[bytes, Dict[bytes, bytes]]]
    ) -> None:
        """Process a batch of messages with priority sorting."""
        # Parse events
        events: List[Tuple[bytes, Event]] = []
        for msg_id, data in messages:
            try:
                event = Event.from_redis(data)
                events.append((msg_id, event))
            except Exception as e:
                logger.error(f"Failed to parse event {msg_id}: {e}")
                # ACK invalid message to prevent reprocessing
                await self.redis.xack(topic, self.config.consumer_group, msg_id)
                messages_processed.labels(topic=topic, status="parse_error").inc()
        
        # Sort by priority
        sorted_events = sorted(
            events,
            key=lambda x: self.priority_weights.get(x[1].meta.priority.value, 0),
            reverse=True
        )
        
        # Process events
        for msg_id, event in sorted_events:
            await self._process_single_event(stream_config, topic, msg_id, event)
    
    async def _process_single_event(
        self,
        stream_config: StreamConfig,
        topic: str,
        msg_id: bytes,
        event: Event
    ) -> None:
        """Process a single event."""
        # Rate limiting
        if not self.global_limiter.acquire():
            logger.warning(f"Global rate limit exceeded, delaying event {event.event_id}")
            await asyncio.sleep(0.1)
            return
        
        if not self.topic_limiters[topic].acquire():
            logger.warning(f"Topic {topic} rate limit exceeded, delaying event {event.event_id}")
            await asyncio.sleep(0.1)
            return
        
        # Start tracing span
        with tracer.start_as_current_span(
            f"process_event_{event.event_type}",
            attributes={
                "event.id": event.event_id,
                "event.topic": topic,
                "event.type": event.event_type,
                "event.priority": event.meta.priority.value,
                "event.retries": event.meta.retries,
            }
        ) as span:
            if event.meta.trace_id:
                span.set_attribute("trace.parent_id", event.meta.trace_id)
            
            start_time = time.time()
            success = False
            
            try:
                # Get handlers for this topic
                topic_handlers = self.handlers.get(topic, [])
                if not topic_handlers:
                    logger.warning(f"No handlers registered for topic {topic}")
                    await self.redis.xack(topic, self.config.consumer_group, msg_id)
                    return
                
                # Execute all handlers
                for handler in topic_handlers:
                    try:
                        await handler(event)
                    except Exception as e:
                        logger.error(
                            f"Handler {handler.__name__} failed for event {event.event_id}: {e}",
                            exc_info=True
                        )
                        raise ConsumerError(f"Handler {handler.__name__} failed") from e
                
                # Success - ACK the message
                await self.redis.xack(topic, self.config.consumer_group, msg_id)
                success = True
                messages_processed.labels(topic=topic, status="success").inc()
                span.set_status(Status(StatusCode.OK))
                
            except Exception as e:
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.record_exception(e)
                
                # Handle retry logic
                if event.meta.retries >= stream_config.retry_limit:
                    # Move to DLQ
                    await self._send_to_dlq(topic, msg_id, event, str(e))
                    # ACK original to remove from stream
                    await self.redis.xack(topic, self.config.consumer_group, msg_id)
                    messages_processed.labels(topic=topic, status="dlq").inc()
                else:
                    # Increment retry count and requeue
                    # For now, we'll let Redis retry via consumer group mechanism
                    logger.warning(
                        f"Event {event.event_id} failed, retry {event.meta.retries + 1}/{stream_config.retry_limit}"
                    )
                    messages_processed.labels(topic=topic, status="retry").inc()
            
            finally:
                # Record metrics
                duration = time.time() - start_time
                processing_duration.labels(topic=topic).observe(duration)
    
    async def _send_to_dlq(
        self, 
        original_topic: str,
        msg_id: bytes,
        event: Event,
        error: str
    ) -> None:
        """Send event to dead letter queue."""
        try:
            dlq_event = event.model_copy(update={
                "topic": self.config.dead_letter_stream,
                "event_type": "dead_letter",
                "payload": {
                    "original_topic": original_topic,
                    "original_msg_id": msg_id.decode(),
                    "original_event": event.model_dump(),
                    "error": error,
                    "failed_at": datetime.utcnow().isoformat()
                }
            })
            
            await self.redis.xadd(
                self.config.dead_letter_stream,
                dlq_event.to_redis(),
                maxlen=1_000_000  # Keep last 1M DLQ events
            )
            
            dlq_messages.labels(topic=original_topic, reason="retry_exhausted").inc()
            logger.error(f"Sent event {event.event_id} to DLQ: {error}")
            
        except Exception as e:
            logger.critical(f"Failed to send event to DLQ: {e}", exc_info=True)
            raise DeadLetterError(f"Failed to send to DLQ: {e}") from e
    
    async def _run_metrics_server(self) -> None:
        """Run Prometheus metrics server."""
        from prometheus_client import start_http_server
        start_http_server(self.config.metrics_port)
        logger.info(f"Metrics server started on port {self.config.metrics_port}")
