"""Goal Scheduler - main scheduling loop and executor."""

import asyncio
import logging
import time
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any

from croniter import croniter
import redis.asyncio as aioredis

from goal_scheduler.config import SchedulerConfig
from goal_scheduler.models import (
    GoalConfig, GoalInstance, GoalState, 
    StepType, EventTrigger
)
from goal_scheduler.storage import GoalStorage
from goal_scheduler.loader import GoalLoader
from goal_scheduler.template_engine import TemplateEngine
from goal_scheduler.executor_simple import StepExecutor

logger = logging.getLogger(__name__)


class GoalScheduler:
    """Main scheduler that manages goal execution."""
    
    def __init__(self, config: SchedulerConfig):
        self.config = config
        self.storage = GoalStorage(config)
        self.loader = GoalLoader(config.goals_dir)
        self.template_engine = TemplateEngine()
        self.executor = StepExecutor(config, self.template_engine)
        
        self._running = False
        self._tasks: List[asyncio.Task] = []
        self._active_goals: Dict[str, asyncio.Task] = {}
        
    async def start(self):
        """Start the scheduler."""
        logger.info("Starting Goal Scheduler...")
        
        # Connect to storage
        await self.storage.connect()
        
        # Connect executor
        await self.executor.connect()
        
        # Load goals
        self.loader.load_all()
        
        # Initialize scheduled goals
        await self._initialize_scheduled_goals()
        
        # Start main loop
        self._running = True
        
        # Start scheduler loop
        loop_task = asyncio.create_task(self._scheduler_loop())
        self._tasks.append(loop_task)
        
        # Start event listener
        event_task = asyncio.create_task(self._event_listener())
        self._tasks.append(event_task)
        
        logger.info("Goal Scheduler started")
        
    async def stop(self):
        """Stop the scheduler."""
        logger.info("Stopping Goal Scheduler...")
        self._running = False
        
        # Cancel all tasks
        for task in self._tasks:
            task.cancel()
            
        # Wait for active goals to complete (with timeout)
        if self._active_goals:
            logger.info(f"Waiting for {len(self._active_goals)} active goals to complete...")
            try:
                await asyncio.wait_for(
                    asyncio.gather(*self._active_goals.values(), return_exceptions=True),
                    timeout=30.0
                )
            except asyncio.TimeoutError:
                logger.warning("Timeout waiting for active goals")
                
        # Disconnect
        await self.executor.disconnect()
        await self.storage.disconnect()
        
        logger.info("Goal Scheduler stopped")
        
    async def _scheduler_loop(self):
        """Main scheduler loop that checks for goals to run."""
        while self._running:
            try:
                # Check for ready goals
                ready_instances = await self.storage.get_ready_instances(
                    limit=self.config.max_concurrent_goals - len(self._active_goals)
                )
                
                for instance_id in ready_instances:
                    if len(self._active_goals) >= self.config.max_concurrent_goals:
                        break
                        
                    if instance_id not in self._active_goals:
                        # Start goal execution
                        task = asyncio.create_task(self._run_goal_instance(instance_id))
                        self._active_goals[instance_id] = task
                        
                        # Clean up when done
                        task.add_done_callback(
                            lambda t, iid=instance_id: self._active_goals.pop(iid, None)
                        )
                        
                # Sleep for interval
                await asyncio.sleep(self.config.loop_interval_sec)
                
            except Exception as e:
                logger.error(f"Error in scheduler loop: {e}")
                await asyncio.sleep(self.config.loop_interval_sec)
                
    async def _event_listener(self):
        """Listen for events that trigger goals."""
        # This would connect to Event Bus and listen for triggers
        # For now, placeholder
        logger.info("Event listener started (placeholder)")
        
        while self._running:
            await asyncio.sleep(60)  # Placeholder
            
    async def _initialize_scheduled_goals(self):
        """Initialize next run times for scheduled goals."""
        for goal_id, goal_config in self.loader.goals.items():
            if not goal_config.schedule:
                continue
                
            # Check if there's already a pending instance
            instances = await self.storage.get_instances_by_goal(goal_id)
            has_pending = any(
                inst.state in [GoalState.PENDING, GoalState.IN_PROGRESS] 
                for inst in instances
            )
            
            if not has_pending:
                # Create new instance with next run time
                next_run = self._calculate_next_run(goal_config.schedule)
                if next_run:
                    instance = self._create_instance(goal_config, next_run_ts=next_run)
                    await self.storage.save_instance(instance)
                    logger.info(f"Scheduled goal {goal_id} for {datetime.fromtimestamp(next_run)}")
                    
    def _calculate_next_run(self, schedule: str) -> Optional[float]:
        """Calculate next run time from cron expression."""
        try:
            if schedule.startswith("@every"):
                # Simple interval format: @every 3600s
                interval = int(schedule.split()[1].rstrip('s'))
                return time.time() + interval
            else:
                # Cron expression
                cron = croniter(schedule, datetime.utcnow())
                next_time = cron.get_next(datetime)
                return next_time.timestamp()
        except Exception as e:
            logger.error(f"Invalid schedule expression '{schedule}': {e}")
            return None
            
    def _create_instance(
        self, 
        goal_config: GoalConfig,
        next_run_ts: Optional[float] = None,
        trigger_event: Optional[Dict[str, Any]] = None
    ) -> GoalInstance:
        """Create a new goal instance."""
        instance_id = f"{goal_config.id}_{int(time.time())}_{uuid.uuid4().hex[:8]}"
        
        return GoalInstance(
            id=instance_id,
            goal_id=goal_config.id,
            state=GoalState.PENDING,
            next_run_ts=next_run_ts,
            trigger_event=trigger_event
        )
        
    async def _run_goal_instance(self, instance_id: str):
        """Run a single goal instance."""
        logger.info(f"Starting goal instance: {instance_id}")
        
        try:
            # Get instance
            instance = await self.storage.get_instance(instance_id)
            if not instance:
                logger.error(f"Instance {instance_id} not found")
                return
                
            # Get goal config
            goal_config = self.loader.get_goal(instance.goal_id)
            if not goal_config:
                logger.error(f"Goal config {instance.goal_id} not found")
                await self.storage.update_instance_state(
                    instance_id, GoalState.FAILED, "Goal config not found"
                )
                return
                
            # Update state to IN_PROGRESS
            await self.storage.update_instance_state(instance_id, GoalState.IN_PROGRESS)
            
            # Execute steps
            success = await self._execute_steps(instance, goal_config)
            
            if success:
                # Mark as succeeded
                await self.storage.update_instance_state(instance_id, GoalState.SUCCEEDED)
                
                # Schedule next run if periodic
                if goal_config.schedule:
                    next_run = self._calculate_next_run(goal_config.schedule)
                    if next_run:
                        new_instance = self._create_instance(goal_config, next_run_ts=next_run)
                        await self.storage.save_instance(new_instance)
                        logger.info(f"Scheduled next run of {goal_config.id} at {datetime.fromtimestamp(next_run)}")
            else:
                # Check retry
                if instance.fail_count < goal_config.retry.attempts:
                    # Retry with backoff
                    retry_time = time.time() + (goal_config.retry.backoff_sec * (instance.fail_count + 1))
                    instance.next_run_ts = retry_time
                    instance.state = GoalState.PENDING
                    await self.storage.save_instance(instance)
                    logger.info(f"Retrying goal {instance_id} at {datetime.fromtimestamp(retry_time)}")
                else:
                    # Mark as failed
                    await self.storage.update_instance_state(instance_id, GoalState.FAILED)
                    
                    # Schedule next run anyway if periodic
                    if goal_config.schedule:
                        next_run = self._calculate_next_run(goal_config.schedule)
                        if next_run:
                            new_instance = self._create_instance(goal_config, next_run_ts=next_run)
                            await self.storage.save_instance(new_instance)
                            
        except Exception as e:
            logger.error(f"Error running goal instance {instance_id}: {e}")
            await self.storage.update_instance_state(
                instance_id, GoalState.FAILED, str(e)
            )
            
    async def _execute_steps(
        self, 
        instance: GoalInstance, 
        goal_config: GoalConfig
    ) -> bool:
        """Execute all steps in a goal."""
        # Build context for template rendering
        context = {
            'trigger': instance.trigger_event or {},
            'params': {},  # Could be passed in
            'prev': {}
        }
        
        # Execute each step
        for i in range(instance.current_step, len(goal_config.steps)):
            step = goal_config.steps[i]
            logger.info(f"Executing step {step.id} ({step.type})")
            
            try:
                # Execute step with timeout
                result = await asyncio.wait_for(
                    self.executor.execute_step(step, context),
                    timeout=step.timeout_sec or goal_config.timeout_sec
                )
                
                # Save step result
                await self.storage.increment_step(instance.id, result)
                
                # Update context for next step
                context['prev'] = {'result': result}
                
                logger.info(f"Step {step.id} completed successfully")
                
            except asyncio.TimeoutError:
                error = f"Step {step.id} timed out after {step.timeout_sec}s"
                logger.error(error)
                await self.storage.update_instance_state(instance.id, GoalState.FAILED, error)
                return False
                
            except Exception as e:
                error = f"Step {step.id} failed: {e}"
                logger.error(error)
                await self.storage.update_instance_state(instance.id, GoalState.FAILED, error)
                return False
                
        return True
        
    async def run_goal_now(self, goal_id: str, params: Optional[Dict[str, Any]] = None) -> str:
        """Run a goal immediately."""
        goal_config = self.loader.get_goal(goal_id)
        if not goal_config:
            raise ValueError(f"Goal {goal_id} not found")
            
        # Create instance
        instance = self._create_instance(goal_config, next_run_ts=time.time())
        if params:
            instance.trigger_event = {'params': params}
            
        await self.storage.save_instance(instance)
        
        logger.info(f"Queued goal {goal_id} for immediate execution")
        return instance.id
        
    async def pause_goal(self, instance_id: str):
        """Pause a goal instance."""
        await self.storage.update_instance_state(instance_id, GoalState.PAUSED)
        
    async def resume_goal(self, instance_id: str):
        """Resume a paused goal instance."""
        instance = await self.storage.get_instance(instance_id)
        if instance and instance.state == GoalState.PAUSED:
            instance.state = GoalState.PENDING
            instance.next_run_ts = time.time()
            await self.storage.save_instance(instance)
