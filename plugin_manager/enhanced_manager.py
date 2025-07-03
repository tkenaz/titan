"""Enhanced Plugin Manager with Circuit Breaker and Watchdog."""

import asyncio
import logging
import os
from pathlib import Path
from typing import Dict, List, Optional, Any
import importlib.util
import inspect
import docker
import redis.asyncio as redis

from plugin_manager.circuit_breaker import CircuitBreaker, PluginState
from plugin_manager.watchdog import ContainerWatchdog
from titan_bus import EventBusClient
from titan_bus.config import EventBusConfig

logger = logging.getLogger(__name__)


class Plugin:
    """Enhanced plugin with health tracking."""
    
    def __init__(self, name: str, module: Any, metadata: Dict[str, Any]):
        self.name = name
        self.module = module
        self.metadata = metadata
        self.handler = getattr(module, 'handle', None)
        self.is_async = inspect.iscoroutinefunction(self.handler) if self.handler else False


class EnhancedPluginManager:
    """Plugin Manager with Circuit Breaker and Container Watchdog."""
    
    def __init__(
        self,
        plugin_dir: str = "./plugins",
        docker_client: Optional[docker.DockerClient] = None,
        redis_url: str = "redis://localhost:6379/0",
        event_bus_client: Optional[EventBusClient] = None
    ):
        self.plugin_dir = Path(plugin_dir)
        self.plugins: Dict[str, Plugin] = {}
        self.docker_client = docker_client or docker.from_env()
        self.redis_url = redis_url
        self.event_bus_client = event_bus_client
        
        # Initialize Circuit Breaker and Watchdog
        self.circuit_breaker: Optional[CircuitBreaker] = None
        self.watchdog: Optional[ContainerWatchdog] = None
        self.redis_client: Optional[redis.Redis] = None
    
    async def initialize(self):
        """Initialize the plugin manager and its components."""
        # Connect to Redis
        self.redis_client = redis.from_url(self.redis_url)
        
        # Initialize Circuit Breaker
        self.circuit_breaker = CircuitBreaker(
            redis_client=self.redis_client,
            failure_threshold=5,
            reset_timeout=300  # 5 minutes
        )
        
        # Initialize Watchdog
        self.watchdog = ContainerWatchdog(
            container_ttl_minutes=10,
            check_interval_seconds=60
        )
        
        # Load plugins
        await self.load_plugins()
        
        # Initialize circuit breaker with plugin names
        plugin_names = list(self.plugins.keys())
        await self.circuit_breaker.initialize(plugin_names)
        
        # Start watchdog
        await self.watchdog.start()
        
        # Initial cleanup of any leftover containers
        cleaned = await self.watchdog.cleanup_exited_containers()
        if cleaned > 0:
            logger.info(f"Cleaned up {cleaned} exited containers on startup")
        
        logger.info(f"Plugin Manager initialized with {len(self.plugins)} plugins")
    
    async def shutdown(self):
        """Shutdown plugin manager and cleanup."""
        logger.info("Shutting down Plugin Manager...")
        
        # Stop watchdog
        if self.watchdog:
            await self.watchdog.stop()
        
        # Final cleanup
        if self.watchdog:
            await self.watchdog.cleanup_exited_containers()
        
        # Close Redis connection
        if self.redis_client:
            await self.redis_client.close()
        
        logger.info("Plugin Manager shutdown complete")
    
    async def load_plugins(self):
        """Load all plugins from plugin directory."""
        if not self.plugin_dir.exists():
            logger.warning(f"Plugin directory {self.plugin_dir} does not exist")
            return
        
        for plugin_file in self.plugin_dir.glob("*.py"):
            if plugin_file.name.startswith("_"):
                continue
            
            try:
                plugin_name = plugin_file.stem
                spec = importlib.util.spec_from_file_location(plugin_name, plugin_file)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                
                # Get plugin metadata
                metadata = getattr(module, 'PLUGIN_METADATA', {
                    'name': plugin_name,
                    'version': '1.0.0',
                    'description': f'Plugin {plugin_name}'
                })
                
                # Create plugin instance
                plugin = Plugin(plugin_name, module, metadata)
                self.plugins[plugin_name] = plugin
                
                logger.info(f"Loaded plugin: {plugin_name}")
                
            except Exception as e:
                logger.error(f"Failed to load plugin {plugin_file}: {e}")
    
    async def execute_plugin(
        self,
        plugin_name: str,
        event_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute a plugin with circuit breaker protection."""
        
        # Check if plugin exists
        plugin = self.plugins.get(plugin_name)
        if not plugin:
            return {
                'success': False,
                'error': f'Plugin {plugin_name} not found'
            }
        
        # Check circuit breaker
        if not await self.circuit_breaker.is_plugin_healthy(plugin_name):
            health = await self.circuit_breaker.get_plugin_health(plugin_name)
            return {
                'success': False,
                'error': f'Plugin {plugin_name} is {health.state.value}',
                'disabled_until': health.disabled_until.isoformat() if health.disabled_until else None
            }
        
        # Execute plugin
        try:
            # Add container labels for tracking
            if hasattr(plugin.module, 'REQUIRES_DOCKER') and plugin.module.REQUIRES_DOCKER:
                event_data['docker_labels'] = {
                    'titan.plugin': 'true',
                    'titan.plugin.name': plugin_name,
                    'titan.event.id': event_data.get('event_id', 'unknown')
                }
            
            # Execute the plugin
            if plugin.is_async:
                result = await plugin.handler(event_data, self.docker_client)
            else:
                result = plugin.handler(event_data, self.docker_client)
            
            # Record success
            await self.circuit_breaker.record_success(plugin_name)
            
            return {
                'success': True,
                'plugin': plugin_name,
                'result': result
            }
            
        except Exception as e:
            logger.error(f"Plugin {plugin_name} execution failed: {e}", exc_info=True)
            
            # Record failure
            should_disable = await self.circuit_breaker.record_failure(
                plugin_name,
                e,
                event_data
            )
            
            if should_disable and self.event_bus_client:
                # Publish alert
                await self.event_bus_client.publish(
                    topic="system.v1",
                    event_type="plugin_disabled",
                    payload={
                        "plugin": plugin_name,
                        "reason": str(e),
                        "consecutive_failures": 5
                    }
                )
            
            return {
                'success': False,
                'plugin': plugin_name,
                'error': str(e)
            }
    
    async def get_plugin_status(self) -> Dict[str, Any]:
        """Get status of all plugins including health."""
        status = {
            'total_plugins': len(self.plugins),
            'plugins': {}
        }
        
        # Get health status from circuit breaker
        health_status = await self.circuit_breaker.get_all_health_status()
        
        for plugin_name, plugin in self.plugins.items():
            health = health_status.get(plugin_name, {})
            
            status['plugins'][plugin_name] = {
                'metadata': plugin.metadata,
                'healthy': health.get('healthy', True),
                'state': health.get('state', 'unknown'),
                'success_rate': health.get('success_rate', 100),
                'total_executions': health.get('total_executions', 0),
                'consecutive_failures': health.get('consecutive_failures', 0),
                'last_failure': health.get('last_failure'),
                'disabled_until': health.get('disabled_until')
            }
        
        # Add container stats
        if self.watchdog:
            container_stats = await self.watchdog.get_container_stats()
            status['containers'] = container_stats
        
        return status
    
    async def reset_plugin(self, plugin_name: str) -> bool:
        """Manually reset a plugin to healthy state."""
        if plugin_name not in self.plugins:
            return False
        
        await self.circuit_breaker.reset_plugin(plugin_name)
        return True
    
    async def pause_plugin(self, plugin_name: str, minutes: int = 60) -> bool:
        """Manually pause a plugin."""
        if plugin_name not in self.plugins:
            return False
        
        await self.circuit_breaker.pause_plugin(plugin_name, minutes)
        return True
    
    async def cleanup_containers(self, force: bool = False) -> int:
        """Manually trigger container cleanup."""
        if not self.watchdog:
            return 0
        
        if force:
            return await self.watchdog.force_cleanup_all()
        else:
            exited = await self.watchdog.cleanup_exited_containers()
            expired = await self.watchdog.cleanup_expired_containers()
            return exited + expired


# Event Bus Consumer for plugin events
async def plugin_event_consumer(manager: EnhancedPluginManager, bus_client: EventBusClient):
    """Consume events and route to plugins."""
    
    async def handle_plugin_event(event: Dict[str, Any]):
        """Handle events for plugins."""
        event_type = event.get('event_type')
        payload = event.get('payload', {})
        
        # Route based on event type or payload
        plugin_name = payload.get('plugin') or event_type.replace('_', '-')
        
        if plugin_name in manager.plugins:
            result = await manager.execute_plugin(plugin_name, event)
            logger.info(f"Plugin {plugin_name} result: {result}")
    
    # Subscribe to plugin events
    await bus_client.subscribe(
        topic="plugin.v1",
        group="plugin-manager",
        handler=handle_plugin_event
    )
    
    logger.info("Plugin event consumer started")


async def main():
    """Run the enhanced plugin manager."""
    import sys
    
    # Initialize Event Bus
    bus_config = EventBusConfig()
    bus_client = EventBusClient(bus_config)
    await bus_client.connect()
    
    # Initialize Plugin Manager
    manager = EnhancedPluginManager(
        plugin_dir="./plugins",
        event_bus_client=bus_client
    )
    
    await manager.initialize()
    
    try:
        # Start event consumer
        await plugin_event_consumer(manager, bus_client)
        
        # Keep running
        while True:
            await asyncio.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        await manager.shutdown()
        await bus_client.disconnect()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
