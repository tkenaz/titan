"""Event Bus consumer for Memory Service."""

import asyncio
import logging
from typing import Dict, Any

from memory_service.service import MemoryService
from memory_service.config import MemoryConfig
from memory_service.models import EvaluationRequest
from titan_bus import EventBusClient
from titan_bus.config import EventBusConfig

logger = logging.getLogger(__name__)


class MemoryEventConsumer:
    """Consumes events from Event Bus and saves to memory."""
    
    def __init__(self, memory_service: MemoryService, bus_client: EventBusClient):
        self.memory_service = memory_service
        self.bus_client = bus_client
        self.consumer_group = "memory-service"
        self.topics = ["chat.v1", "system.v1"]
    
    async def start(self):
        """Start consuming events."""
        logger.info(f"Starting Memory consumer for topics: {self.topics}")
        
        # Subscribe to topics
        for topic in self.topics:
            await self.bus_client.subscribe(
                topic=topic,
                group=self.consumer_group,
                handler=self._handle_event
            )
        
        logger.info("Memory consumer started and listening...")
    
    async def _handle_event(self, event: Dict[str, Any]):
        """Handle incoming event."""
        try:
            topic = event.get("topic")
            event_type = event.get("event_type")
            payload = event.get("payload", {})
            
            logger.debug(f"Processing event: {topic}/{event_type}")
            
            # Route based on topic and event type
            if topic == "chat.v1" and event_type == "user_message":
                await self._handle_chat_message(payload)
            
            elif topic == "system.v1" and event_type == "file_summary":
                await self._handle_file_summary(payload)
            
            elif topic == "system.v1" and event_type == "memory_request":
                await self._handle_memory_request(payload)
            
            else:
                logger.debug(f"Ignoring event type: {topic}/{event_type}")
        
        except Exception as e:
            logger.error(f"Error handling event: {e}", exc_info=True)
    
    async def _handle_chat_message(self, payload: Dict[str, Any]):
        """Handle chat message event."""
        message = payload.get("text", "")
        user_id = payload.get("user_id")
        
        if not message:
            return
        
        # Create evaluation request
        request = EvaluationRequest(
            message=message,
            source=f"chat/{user_id}" if user_id else "chat",
            context={
                "user_id": user_id,
                "timestamp": payload.get("timestamp")
            }
        )
        
        # Evaluate and save if important
        response = await self.memory_service.evaluate_and_save(request)
        
        if response.saved:
            logger.info(f"Saved chat message to memory: {response.id}")
    
    async def _handle_file_summary(self, payload: Dict[str, Any]):
        """Handle file summary from file_watcher."""
        message = payload.get("message", "")
        context = payload.get("context", {})
        
        if not message:
            return
        
        # File events are usually important
        request = EvaluationRequest(
            message=message,
            source=payload.get("source", "file_watcher"),
            context=context,
            force_save=context.get("importance") == "high"
        )
        
        response = await self.memory_service.evaluate_and_save(request)
        
        if response.saved:
            logger.info(f"Saved file event to memory: {response.id}")
            
            # Publish confirmation back
            await self.bus_client.publish(
                topic="system.v1",
                event_type="memory_saved",
                payload={
                    "memory_id": response.id,
                    "original_event": "file_summary",
                    "file_path": context.get("file_path")
                }
            )
    
    async def _handle_memory_request(self, payload: Dict[str, Any]):
        """Handle explicit memory request."""
        message = payload.get("message", "")
        
        if not message:
            return
        
        # Force save for explicit requests
        request = EvaluationRequest(
            message=message,
            source=payload.get("source", "explicit"),
            context=payload.get("context", {}),
            force_save=True
        )
        
        response = await self.memory_service.evaluate_and_save(request)
        logger.info(f"Force saved memory: {response.id}")


async def run_consumer():
    """Run the memory consumer."""
    # Load config
    config = MemoryConfig.from_yaml('config/memory.yaml')
    
    # Initialize services
    memory_service = MemoryService(config)
    await memory_service.connect()
    
    # Initialize Event Bus
    bus_config = EventBusConfig(
        redis={"url": config.event_bus_url}
    )
    bus_client = EventBusClient(bus_config)
    await bus_client.connect()
    
    # Create and start consumer
    consumer = MemoryEventConsumer(memory_service, bus_client)
    await consumer.start()
    
    try:
        # Keep running
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutting down Memory consumer...")
    finally:
        await memory_service.disconnect()
        await bus_client.disconnect()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    asyncio.run(run_consumer())
