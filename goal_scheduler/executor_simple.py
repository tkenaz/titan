"""Goal Scheduler - simplified executor without Event Bus for MVP."""

import asyncio
import logging
import json
from typing import Dict, Any, Optional

from goal_scheduler.config import SchedulerConfig
from goal_scheduler.models import GoalStep, StepType
from goal_scheduler.template_engine import TemplateEngine

logger = logging.getLogger(__name__)


class StepExecutor:
    """Execute different types of goal steps."""
    
    def __init__(self, config: SchedulerConfig, template_engine: TemplateEngine):
        self.config = config
        self.template_engine = template_engine
        self._plugin_results: Dict[str, asyncio.Future] = {}
        
    async def connect(self):
        """Connect to services (simplified for MVP)."""
        logger.info("StepExecutor connected (Event Bus disabled for MVP)")
        
    async def disconnect(self):
        """Disconnect from services."""
        pass
        
    async def execute_step(
        self, 
        step: GoalStep, 
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute a single step based on its type."""
        # Render step parameters with context
        if step.params:
            rendered_params = self.template_engine.render_dict(step.params, context)
        else:
            rendered_params = {}
            
        if step.type == StepType.PLUGIN:
            return await self._execute_plugin_step(step, rendered_params, context)
        elif step.type == StepType.BUS_EVENT:
            return await self._execute_bus_event_step(step, rendered_params, context)
        elif step.type == StepType.INTERNAL:
            return await self._execute_internal_step(step, rendered_params, context)
        else:
            raise ValueError(f"Unknown step type: {step.type}")
            
    async def _execute_plugin_step(
        self, 
        step: GoalStep, 
        params: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute a plugin step (simplified for MVP)."""
        logger.info(f"Would execute plugin: {step.plugin} with params: {params}")
        
        # For MVP, just return success
        return {
            "status": "simulated",
            "plugin": step.plugin,
            "params": params,
            "message": "Plugin execution simulated (Event Bus not connected)"
        }
            
    async def _execute_bus_event_step(
        self, 
        step: GoalStep,
        params: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute a bus event step (simplified for MVP)."""
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
            
        logger.info(f"Would publish to {step.topic}/{step.event_type}: {payload}")
        
        return {
            "status": "simulated",
            "topic": step.topic,
            "event_type": step.event_type,
            "payload": payload,
            "message": "Event publish simulated (Event Bus not connected)"
        }
        
    async def _execute_internal_step(
        self,
        step: GoalStep,
        params: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute internal step."""
        logger.info(f"Executing internal step: {step.id} with params: {params}")
        
        return {
            "status": "completed",
            "step_id": step.id,
            "params": params
        }
