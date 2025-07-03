"""Event Bus integration for Plugin Manager."""

import asyncio
import logging
from typing import Optional

from plugin_manager.config import PluginManagerConfig
from plugin_manager.manager import PluginManager

try:
    from titan_bus import EventBusClient, Event
    TITAN_BUS_AVAILABLE = True
except ImportError:
    logger = logging.getLogger(__name__)
    logger.warning("titan_bus not available, Event Bus integration disabled")
    TITAN_BUS_AVAILABLE = False
    Event = None
    EventBusClient = None


logger = logging.getLogger(__name__)


class PluginEventBusIntegration:
    """Integration between Plugin Manager and Titan Event Bus."""
    
    def __init__(self, config: PluginManagerConfig, plugin_manager: PluginManager):
        self.config = config
        self.plugin_manager = plugin_manager
        self.event_client: Optional[EventBusClient] = None
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
        
        # Subscribe to all topics (plugins will filter)
        topics = ["chat.v1", "fs.v1", "system.v1", "memory.v1"]
        
        for topic in topics:
            self.event_client.subscribe(topic, self._handle_event)
        
        # Start processor
        await self.event_client.start_processor()
        
        self._running = True
        logger.info("Plugin Event Bus integration started")
    
    async def stop(self):
        """Stop event processing."""
        if not self._running:
            return
        
        if self.event_client:
            await self.event_client.disconnect()
        
        self._running = False
        logger.info("Plugin Event Bus integration stopped")
    
    async def _handle_event(self, event: Event):
        """Handle incoming event from Event Bus."""
        try:
            # Convert Event to dict for plugin dispatch
            event_dict = {
                "event_id": event.event_id,
                "topic": event.topic,
                "event_type": event.event_type,
                "timestamp": event.timestamp.isoformat(),
                "payload": event.payload,
                "meta": event.meta
            }
            
            # Dispatch to plugins
            dispatched = await self.plugin_manager.dispatch_event(event_dict)
            
            if dispatched:
                logger.info(
                    f"Event {event.event_id} dispatched to plugins: {dispatched}"
                )
            
        except Exception as e:
            logger.error(f"Error handling event: {e}", exc_info=True)
    
    async def publish_plugin_event(
        self,
        event_type: str,
        payload: dict,
        source_plugin: str
    ):
        """Publish event from a plugin."""
        if not self.event_client:
            logger.warning("Event client not initialized")
            return
        
        # Add plugin source to payload
        payload["source_plugin"] = source_plugin
        
        await self.event_client.publish(
            topic="plugin.v1",
            event_type=event_type,
            payload=payload
        )
