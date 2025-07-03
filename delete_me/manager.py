"""Core Plugin Manager implementation."""

import asyncio
import logging
import signal
from pathlib import Path
from typing import Dict, List, Optional, Set
from datetime import datetime

from plugin_manager.config import PluginManagerConfig
from plugin_manager.models import (
    PluginConfig, PluginInstance, PluginStatus,
    PluginTask, PluginResult, EventTrigger
)
from plugin_manager.sandbox import SandboxExecutor


logger = logging.getLogger(__name__)


class PluginManager:
    """Manages plugin lifecycle and event dispatch."""
    
    def __init__(self, config: PluginManagerConfig):
        self.config = config
        self.plugins: Dict[str, PluginInstance] = {}
        self.trigger_map: Dict[str, Set[str]] = {}  # trigger_key -> plugin_names
        self.sandbox = SandboxExecutor(config.sandbox)
        
        # Task queue
        self.task_queue: asyncio.Queue = asyncio.Queue(maxsize=config.task_queue_size)
        self.workers: List[asyncio.Task] = []
        self.running = False
        
        # Setup signal handlers
        signal.signal(signal.SIGHUP, self._handle_reload_signal)
    
    async def start(self):
        """Start plugin manager."""
        if self.running:
            return
        
        self.running = True
        
        # Discover and load plugins
        await self.discover_plugins()
        
        # Start worker tasks
        for i in range(self.config.max_concurrent_plugins):
            worker = asyncio.create_task(self._worker(f"worker-{i}"))
            self.workers.append(worker)
        
        logger.info(f"Plugin Manager started with {len(self.plugins)} plugins")
    
    async def stop(self):
        """Stop plugin manager."""
        if not self.running:
            return
        
        self.running = False
        
        # Cancel workers
        for worker in self.workers:
            worker.cancel()
        
        await asyncio.gather(*self.workers, return_exceptions=True)
        self.workers.clear()
        
        logger.info("Plugin Manager stopped")
    
    async def discover_plugins(self) -> List[str]:
        """Discover and load plugins from plugins directory."""
        loaded = []
        
        # Create plugins directory if not exists
        self.config.plugins_dir.mkdir(exist_ok=True)
        
        # Scan for plugin directories
        for plugin_dir in self.config.plugins_dir.iterdir():
            if not plugin_dir.is_dir():
                continue
            
            plugin_yaml = plugin_dir / "plugin.yaml"
            if not plugin_yaml.exists():
                continue
            
            try:
                # Load plugin config
                config = PluginConfig.from_yaml(plugin_yaml)
                
                # Prepare plugin image if needed
                if config.requirements:
                    success = await self.sandbox.prepare_plugin_image(config, plugin_dir)
                    if not success:
                        logger.error(f"Failed to prepare image for {config.name}")
                        continue
                
                # Create plugin instance
                instance = PluginInstance(
                    config=config,
                    path=plugin_dir,
                    status=PluginStatus.LOADED
                )
                
                self.plugins[config.name] = instance
                self._update_trigger_map(config)
                
                loaded.append(config.name)
                logger.info(f"Loaded plugin: {config.name} v{config.version}")
                
            except Exception as e:
                logger.error(f"Failed to load plugin from {plugin_dir}: {e}")
        
        return loaded
    
    def _update_trigger_map(self, config: PluginConfig):
        """Update trigger mapping for efficient dispatch."""
        for trigger in config.triggers:
            key = self._make_trigger_key(trigger)
            if key not in self.trigger_map:
                self.trigger_map[key] = set()
            self.trigger_map[key].add(config.name)
    
    def _make_trigger_key(self, trigger: EventTrigger) -> str:
        """Create a key for trigger lookup."""
        if trigger.event_type:
            return f"{trigger.topic}:{trigger.event_type}"
        return trigger.topic
    
    async def dispatch_event(self, event: Dict) -> List[str]:
        """Dispatch event to matching plugins."""
        dispatched = []
        
        # Extract event info
        topic = event.get("topic", "")
        event_type = event.get("event_type", "")
        event_id = event.get("event_id", "")
        
        # Find matching plugins
        keys_to_check = [
            f"{topic}:{event_type}",
            topic
        ]
        
        matching_plugins = set()
        for key in keys_to_check:
            if key in self.trigger_map:
                matching_plugins.update(self.trigger_map[key])
        
        # Queue tasks for matching plugins
        for plugin_name in matching_plugins:
            if plugin_name not in self.plugins:
                continue
            
            plugin = self.plugins[plugin_name]
            
            # Check additional filters
            if not self._check_event_filters(plugin.config, event):
                continue
            
            # Create task
            task = PluginTask(
                plugin_name=plugin_name,
                event=event,
                event_id=event_id,
                timestamp=datetime.utcnow().isoformat()
            )
            
            try:
                await self.task_queue.put(task)
                dispatched.append(plugin_name)
                logger.debug(f"Queued task for plugin {plugin_name}")
            except asyncio.QueueFull:
                logger.error(f"Task queue full, dropping task for {plugin_name}")
        
        return dispatched
    
    def _check_event_filters(self, config: PluginConfig, event: Dict) -> bool:
        """Check if event matches plugin filters."""
        for trigger in config.triggers:
            if not trigger.filter:
                return True
            
            # Simple filter matching (in production, use jsonpath or similar)
            payload = event.get("payload", {})
            for key, expected in trigger.filter.items():
                if payload.get(key) != expected:
                    return False
        
        return True
    
    async def _worker(self, name: str):
        """Worker coroutine to process plugin tasks."""
        logger.info(f"Worker {name} started")
        
        while self.running:
            try:
                # Get task with timeout
                task = await asyncio.wait_for(
                    self.task_queue.get(),
                    timeout=1.0
                )
                
                # Execute plugin
                await self._execute_plugin(task)
                
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Worker {name} error: {e}")
        
        logger.info(f"Worker {name} stopped")
    
    async def _execute_plugin(self, task: PluginTask):
        """Execute a plugin task."""
        plugin_name = task.plugin_name
        
        if plugin_name not in self.plugins:
            logger.error(f"Plugin {plugin_name} not found")
            return
        
        plugin = self.plugins[plugin_name]
        
        # Update status
        plugin.status = PluginStatus.RUNNING
        plugin.last_run = datetime.utcnow().isoformat()
        
        try:
            # Execute in sandbox
            result = await self.sandbox.execute(
                plugin.config,
                plugin.path,
                task
            )
            
            # Update metrics
            plugin.invocation_count += 1
            if not result.success:
                plugin.error_count += 1
                plugin.status = PluginStatus.ERROR
                plugin.error = result.error or f"Exit code: {result.exit_code}"
            else:
                plugin.status = PluginStatus.LOADED
                plugin.error = None
            
            # Log result
            if result.success:
                logger.info(f"Plugin {plugin_name} completed successfully")
            else:
                logger.error(f"Plugin {plugin_name} failed: {result.error}")
            
            # Emit metrics (implement later)
            await self._emit_metrics(plugin, result)
            
        except Exception as e:
            logger.error(f"Failed to execute plugin {plugin_name}: {e}")
            plugin.status = PluginStatus.ERROR
            plugin.error = str(e)
            plugin.error_count += 1
    
    async def _emit_metrics(self, plugin: PluginInstance, result: PluginResult):
        """Emit Prometheus metrics."""
        # TODO: Implement metrics emission
        pass
    
    async def reload_plugins(self):
        """Reload plugins (hot reload)."""
        logger.info("Reloading plugins...")
        
        # Discover new/updated plugins
        current_plugins = set(self.plugins.keys())
        loaded = await self.discover_plugins()
        new_plugins = set(loaded)
        
        # Find removed plugins
        removed = current_plugins - new_plugins
        for name in removed:
            logger.info(f"Removing plugin: {name}")
            del self.plugins[name]
        
        # Rebuild trigger map
        self.trigger_map.clear()
        for plugin in self.plugins.values():
            self._update_trigger_map(plugin.config)
        
        logger.info(f"Reload complete. Active plugins: {len(self.plugins)}")
    
    def _handle_reload_signal(self, signum, frame):
        """Handle SIGHUP for hot reload."""
        logger.info("Received SIGHUP, scheduling reload...")
        asyncio.create_task(self.reload_plugins())
    
    def get_plugin_status(self) -> Dict[str, Dict]:
        """Get status of all plugins."""
        status = {}
        
        for name, plugin in self.plugins.items():
            status[name] = {
                "version": plugin.config.version,
                "status": plugin.status.value,
                "invocations": plugin.invocation_count,
                "errors": plugin.error_count,
                "last_run": plugin.last_run,
                "error": plugin.error
            }
        
        return status
    
    async def trigger_plugin_manually(
        self,
        plugin_name: str,
        event_data: Dict
    ) -> PluginResult:
        """Manually trigger a plugin (for testing)."""
        if plugin_name not in self.plugins:
            raise ValueError(f"Plugin {plugin_name} not found")
        
        plugin = self.plugins[plugin_name]
        
        # Create synthetic task
        task = PluginTask(
            plugin_name=plugin_name,
            event=event_data,
            event_id=f"manual-{datetime.utcnow().timestamp()}",
            timestamp=datetime.utcnow().isoformat()
        )
        
        # Execute directly (bypass queue)
        result = await self.sandbox.execute(
            plugin.config,
            plugin.path,
            task
        )
        
        return result
