"""Event Bus integration for Memory Service."""

import asyncio
import logging
from typing import Dict, Any

try:
    from titan_bus import EventBusClient, Event, subscribe
    TITAN_BUS_AVAILABLE = True
except ImportError:
    logger = logging.getLogger(__name__)
    logger.warning("titan_bus not available, Event Bus integration disabled")
    TITAN_BUS_AVAILABLE = False
    Event = None
    EventBusClient = None
from memory_service.config import MemoryConfig
from memory_service.service import MemoryService
from memory_service.models import EvaluationRequest


logger = logging.getLogger(__name__)


class MemoryEventHandler:
    """Handle events from Titan Event Bus."""
    
    def __init__(self, memory_service: MemoryService):
        self.memory_service = memory_service
    
    async def handle_chat_event(self, event: Event):
        """Process chat events for memory extraction."""
        try:
            # Extract message from event
            payload = event.payload
            message = payload.get("text", "")
            user_id = payload.get("user_id")
            
            if not message:
                return
            
            # Evaluate and save
            request = EvaluationRequest(
                message=message,
                context={
                    "event_id": event.event_id,
                    "event_type": event.event_type,
                    "user_id": user_id,
                    "timestamp": event.timestamp.isoformat()
                },
                source="chat.v1"
            )
            
            response = await self.memory_service.evaluate_and_save(request)
            
            if response.saved:
                logger.info(f"Saved memory from chat event: {response.id}")
            
        except Exception as e:
            logger.error(f"Error handling chat event: {e}", exc_info=True)
    
    async def handle_system_event(self, event: Event):
        """Process system events."""
        try:
            event_type = event.event_type
            
            if event_type == "memory_gc_requested":
                # Run garbage collection
                deleted = await self.memory_service.garbage_collect()
                logger.info(f"GC triggered by system event, deleted {len(deleted)} memories")
            
            elif event_type == "memory_save_requested":
                # Explicit save request
                payload = event.payload
                request = EvaluationRequest(
                    message=payload.get("text", ""),
                    context=payload.get("context", {}),
                    source="system.v1"
                )
                
                response = await self.memory_service.evaluate_and_save(request)
                logger.info(f"System save request: {response}")
                
        except Exception as e:
            logger.error(f"Error handling system event: {e}", exc_info=True)


class MemoryEventBusIntegration:
    """Integration with Titan Event Bus."""
    
    def __init__(self, config: MemoryConfig, memory_service: MemoryService):
        self.config = config
        self.memory_service = memory_service
        self.event_client = None
        self.handler = MemoryEventHandler(memory_service)
        self._running = False
    
    async def start(self):
        """Start listening to events."""
        if not TITAN_BUS_AVAILABLE:
            logger.warning("Titan Bus not available, skipping Event Bus integration")
            return
            
        if self._running:
            return
        
        # Create event bus client
        from titan_bus.config import EventBusConfig
        bus_config = EventBusConfig(
            redis={"url": self.config.event_bus_url},
            consumer_group=self.config.consumer_group
        )
        
        self.event_client = EventBusClient(bus_config)
        await self.event_client.connect()
        
        # Subscribe to topics
        self.event_client.subscribe("chat.v1", self.handler.handle_chat_event)
        self.event_client.subscribe("system.v1", self.handler.handle_system_event)
        
        # Start processor
        await self.event_client.start_processor()
        
        self._running = True
        logger.info("Memory Event Bus integration started")
    
    async def stop(self):
        """Stop event processing."""
        if not self._running:
            return
        
        if self.event_client:
            await self.event_client.disconnect()
        
        self._running = False
        logger.info("Memory Event Bus integration stopped")
    
    async def publish_memory_event(
        self,
        event_type: str,
        payload: Dict[str, Any]
    ):
        """Publish memory-related events."""
        if not self.event_client:
            logger.warning("Event client not initialized")
            return
        
        await self.event_client.publish(
            topic="memory.v1",
            event_type=event_type,
            payload=payload
        )
