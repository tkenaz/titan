"""Example: Goal Scheduler Integration with Titan Event Bus."""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Any
from dataclasses import dataclass
from enum import Enum

from titan_bus import subscribe, publish, Event, EventPriority


class GoalStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Goal:
    """Represents an autonomous goal."""
    id: str
    name: str
    trigger_type: str  # "cron", "event", "manual"
    trigger_config: Dict[str, Any]
    steps: List[Dict[str, Any]]
    status: GoalStatus = GoalStatus.PENDING
    context: Dict[str, Any] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for event payload."""
        return {
            "id": self.id,
            "name": self.name,
            "trigger_type": self.trigger_type,
            "trigger_config": self.trigger_config,
            "steps": self.steps,
            "status": self.status.value,
            "context": self.context or {}
        }


class GoalScheduler:
    """Simple goal scheduler integrated with Titan Event Bus."""
    
    def __init__(self):
        self.goals: Dict[str, Goal] = {}
        self.running = False
        self._tasks = set()
        
        # Subscribe to goal-related events
        subscribe("system.v1", self.handle_system_event)
        subscribe("fs.v1", self.handle_file_event)
    
    async def handle_system_event(self, event: Event):
        """Handle system events that might trigger goals."""
        if event.event_type == "goal_created":
            goal_data = event.payload
            goal = Goal(**goal_data)
            await self.add_goal(goal)
        
        elif event.event_type == "goal_execute":
            goal_id = event.payload.get("goal_id")
            await self.execute_goal(goal_id)
    
    async def handle_file_event(self, event: Event):
        """Handle file events that might trigger goals."""
        # Check if any goals are triggered by file events
        for goal in self.goals.values():
            if goal.trigger_type == "event" and goal.trigger_config.get("event_type") == event.event_type:
                # Check if file matches pattern
                pattern = goal.trigger_config.get("file_pattern", "*")
                file_path = event.payload.get("path", "")
                
                if self._matches_pattern(file_path, pattern):
                    await self.execute_goal(goal.id, trigger_event=event)
    
    async def add_goal(self, goal: Goal):
        """Add a new goal to the scheduler."""
        self.goals[goal.id] = goal
        
        # Publish goal created event
        await publish(
            topic="system.v1",
            event_type="goal_registered",
            payload=goal.to_dict(),
            priority=EventPriority.LOW
        )
        
        # Schedule if it's a cron-based goal
        if goal.trigger_type == "cron":
            task = asyncio.create_task(self._schedule_cron_goal(goal))
            self._tasks.add(task)
            task.add_done_callback(self._tasks.discard)
    
    async def execute_goal(self, goal_id: str, trigger_event: Event = None):
        """Execute a goal's steps."""
        goal = self.goals.get(goal_id)
        if not goal:
            return
        
        # Update status
        goal.status = GoalStatus.IN_PROGRESS
        await self._publish_goal_status(goal)
        
        try:
            # Execute each step
            for i, step in enumerate(goal.steps):
                await self._execute_step(goal, i, step, trigger_event)
            
            # Mark as completed
            goal.status = GoalStatus.COMPLETED
            await self._publish_goal_status(goal)
            
        except Exception as e:
            # Mark as failed
            goal.status = GoalStatus.FAILED
            await self._publish_goal_status(goal, error=str(e))
    
    async def _execute_step(self, goal: Goal, step_index: int, step: Dict[str, Any], trigger_event: Event = None):
        """Execute a single step of a goal."""
        action = step.get("action")
        params = step.get("params", {})
        
        # Add context
        params["goal_id"] = goal.id
        params["step_index"] = step_index
        if trigger_event:
            params["trigger_event"] = trigger_event.model_dump()
        
        # Publish step execution event
        await publish(
            topic="system.v1",
            event_type=f"goal_step_{action}",
            payload=params,
            priority=EventPriority.MEDIUM
        )
        
        # Simulate step execution
        await asyncio.sleep(0.5)
    
    async def _publish_goal_status(self, goal: Goal, error: str = None):
        """Publish goal status update."""
        payload = goal.to_dict()
        if error:
            payload["error"] = error
        
        await publish(
            topic="system.v1",
            event_type="goal_status_changed",
            payload=payload,
            priority=EventPriority.LOW
        )
    
    async def _schedule_cron_goal(self, goal: Goal):
        """Schedule a cron-based goal."""
        # Simple implementation - in production use APScheduler
        interval = goal.trigger_config.get("interval_seconds", 3600)
        
        while self.running:
            await asyncio.sleep(interval)
            await self.execute_goal(goal.id)
    
    def _matches_pattern(self, path: str, pattern: str) -> bool:
        """Check if file path matches pattern."""
        from fnmatch import fnmatch
        return fnmatch(path, pattern)


# Example usage
async def main():
    """Example goal scheduler setup."""
    scheduler = GoalScheduler()
    scheduler.running = True
    
    # Create a file-triggered goal
    file_goal = Goal(
        id="process_pdfs",
        name="Process new PDF files",
        trigger_type="event",
        trigger_config={
            "event_type": "file_created",
            "file_pattern": "*.pdf"
        },
        steps=[
            {"action": "extract_text", "params": {}},
            {"action": "create_embeddings", "params": {}},
            {"action": "update_index", "params": {}}
        ]
    )
    
    await scheduler.add_goal(file_goal)
    
    # Create a scheduled goal
    scheduled_goal = Goal(
        id="daily_summary",
        name="Generate daily summary",
        trigger_type="cron",
        trigger_config={
            "interval_seconds": 86400  # Daily
        },
        steps=[
            {"action": "collect_events", "params": {"hours": 24}},
            {"action": "generate_summary", "params": {}},
            {"action": "send_notification", "params": {}}
        ]
    )
    
    await scheduler.add_goal(scheduled_goal)
    
    print("Goal scheduler running...")
    
    # Keep running
    try:
        await asyncio.Event().wait()
    except KeyboardInterrupt:
        scheduler.running = False


if __name__ == "__main__":
    asyncio.run(main())
