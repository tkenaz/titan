"""Step executor for different step types."""

import asyncio
import logging
import json
import time
from typing import Dict, Any, Optional

from goal_scheduler.config import SchedulerConfig
from goal_scheduler.models import GoalStep, StepType
from goal_scheduler.template_engine import TemplateEngine
from goal_scheduler.metrics import goal_step_duration_seconds

logger = logging.getLogger(__name__)

# Try to import titan_bus
try:
    from titan_bus import EventBusClient, publish
    from titan_bus.config import EventBusConfig
    TITAN_BUS_AVAILABLE = True
except ImportError:
    logger.warning("titan_bus not available, Event Bus integration disabled")
    TITAN_BUS_AVAILABLE = False
    EventBusClient = None
    EventBusConfig = None
    publish = None


class StepExecutor:
    """Execute different types of goal steps."""
    
    def __init__(self, config: SchedulerConfig, template_engine: TemplateEngine):
        self.config = config
        self.template_engine = template_engine
        self.event_bus: Optional[EventBusClient] = None
        self._plugin_results: Dict[str, asyncio.Future] = {}
        
    async def connect(self):
        """Connect to Event Bus."""
        if TITAN_BUS_AVAILABLE:
            # IMPORTANT: Create config without allowing env override
            import os
            
            # Temporarily clear TITAN env vars to prevent override
            titan_env_backup = {}
            for key in list(os.environ.keys()):
                if key.startswith('TITAN_'):
                    titan_env_backup[key] = os.environ.pop(key)
            
            try:
                # Create EventBusConfig with proper Redis config
                from titan_bus.config import RedisConfig
                
                logger.info(f"Creating RedisConfig with URL: {self.config.event_bus_url}")
                
                redis_config = RedisConfig(url=self.config.event_bus_url)
                logger.info(f"RedisConfig created with URL: {redis_config.url}")
                
                # Create EventBusConfig with our Redis config
                bus_config = EventBusConfig(redis=redis_config)
                logger.info(f"EventBusConfig redis.url: {bus_config.redis.url}")
                
                self.event_bus = EventBusClient(bus_config)
                await self.event_bus.connect()
            finally:
                # Restore env vars
                os.environ.update(titan_env_backup)
            
            # Subscribe to plugin results
            self.event_bus.subscribe(
                "plugin.result",
                self._handle_plugin_result
            )
            
            logger.info("Connected to Event Bus for step execution")
        else:
            logger.warning("Event Bus not available, plugin steps will fail")
            
    async def disconnect(self):
        """Disconnect from Event Bus."""
        if self.event_bus:
            await self.event_bus.disconnect()
            
    async def execute_step(
        self, 
        step: GoalStep, 
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute a single step based on its type."""
        start_time = time.time()
        goal_id = context.get('goal_instance', {}).get('goal_id', 'unknown')
        
        try:
            # Render step parameters with context
            if step.params:
                rendered_params = self.template_engine.render_dict(step.params, context)
            else:
                rendered_params = {}
                
            if step.type == StepType.PLUGIN:
                result = await self._execute_plugin_step(step, rendered_params, context)
            elif step.type == StepType.BUS_EVENT:
                result = await self._execute_bus_event_step(step, rendered_params, context)
            elif step.type == StepType.INTERNAL:
                result = await self._execute_internal_step(step, rendered_params, context)
            else:
                raise ValueError(f"Unknown step type: {step.type}")
                
            # Record step duration
            duration = time.time() - start_time
            goal_step_duration_seconds.labels(
                goal=goal_id,
                step=step.id
            ).observe(duration)
            
            return result
            
        except Exception as e:
            # Record step duration even on failure
            duration = time.time() - start_time
            goal_step_duration_seconds.labels(
                goal=goal_id,
                step=step.id
            ).observe(duration)
            raise
            
    async def _execute_plugin_step(
        self, 
        step: GoalStep, 
        params: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute a plugin step via Event Bus."""
        if not TITAN_BUS_AVAILABLE or not self.event_bus:
            raise RuntimeError("Event Bus not available for plugin execution")
            
        # Create correlation ID for tracking response
        correlation_id = f"{step.id}_{asyncio.current_task().get_name()}"
        
        # Create future for result
        result_future = asyncio.Future()
        self._plugin_results[correlation_id] = result_future
        
        try:
            # Publish plugin execution request
            event_data = {
                "plugin": step.plugin,
                "params": params,
                "correlation_id": correlation_id,
                "timeout": step.timeout_sec
            }
            
            await publish(
                topic="plugin.v1",
                event_type="execute",
                payload=event_data
            )
            
            logger.info(f"Published plugin execution request: {step.plugin}")
            
            # Wait for result
            result = await asyncio.wait_for(
                result_future,
                timeout=step.timeout_sec
            )
            
            return result
            
        finally:
            # Clean up
            self._plugin_results.pop(correlation_id, None)
            
    async def _execute_bus_event_step(
        self, 
        step: GoalStep,
        params: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute a bus event step."""
        if not TITAN_BUS_AVAILABLE:
            raise RuntimeError("Event Bus not available")
            
        # Prepare payload
        if step.payload_template:
            # Render template
            payload_str = self.template_engine.render(step.payload_template, context)
            try:
                payload = json.loads(payload_str)
            except json.JSONDecodeError:
                # If not JSON, use as string
                payload = {"message": payload_str}
        else:
            payload = params
            
        # Publish event
        await publish(
            topic=step.topic,
            event_type=step.event_type or "goal_step",
            payload=payload
        )
        
        logger.info(f"Published event to {step.topic}/{step.event_type}")
        
        return {
            "status": "published",
            "topic": step.topic,
            "event_type": step.event_type,
            "payload": payload
        }
        
    async def _execute_internal_step(
        self,
        step: GoalStep,
        params: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute internal step (placeholder for future functionality)."""
        # This could be extended to support internal functions
        # For now, just log and return params
        logger.info(f"Executing internal step: {step.id}")
        
        return {
            "status": "completed",
            "step_id": step.id,
            "params": params
        }
        
    async def _handle_plugin_result(self, event: Dict[str, Any]):
        """Handle plugin execution results."""
        correlation_id = event.get("correlation_id")
        if not correlation_id:
            return
            
        future = self._plugin_results.get(correlation_id)
        if not future:
            return
            
        if event.get("success"):
            future.set_result(event.get("result", {}))
        else:
            future.set_exception(
                RuntimeError(f"Plugin execution failed: {event.get('error')}")
            )
