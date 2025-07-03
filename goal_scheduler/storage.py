"""Goal Scheduler storage layer using Redis."""

import time
import logging
from typing import Dict, List, Optional, Set, Any
import redis.asyncio as aioredis
import yaml
from datetime import datetime

from goal_scheduler.models import GoalInstance, GoalState
from goal_scheduler.config import SchedulerConfig

logger = logging.getLogger(__name__)


class GoalStorage:
    """Redis storage for goal state management."""
    
    def __init__(self, config: SchedulerConfig):
        self.config = config
        self.redis: Optional[aioredis.Redis] = None
        
    async def connect(self):
        """Connect to Redis."""
        self.redis = await aioredis.from_url(
            self.config.redis_url,
            decode_responses=True
        )
        logger.info("Connected to Redis for goal storage")
        
    async def disconnect(self):
        """Disconnect from Redis."""
        if self.redis:
            await self.redis.close()
            
    async def save_instance(self, instance: GoalInstance) -> None:
        """Save goal instance to Redis."""
        key = f"goal:{instance.id}"
        await self.redis.hset(key, mapping=instance.to_redis_hash())
        
        # Add to queue if has next_run_ts
        if instance.next_run_ts and instance.state in [GoalState.PENDING, GoalState.IN_PROGRESS]:
            await self.redis.zadd("goal_queue", {instance.id: instance.next_run_ts})
        else:
            # Remove from queue if completed/failed/paused
            await self.redis.zrem("goal_queue", instance.id)
            
        # Add to goal instances set
        await self.redis.sadd(f"goal_instances:{instance.goal_id}", instance.id)
        
        # Set expiration for completed/failed instances (7 days)
        if instance.state in [GoalState.SUCCEEDED, GoalState.FAILED]:
            await self.redis.expire(key, 7 * 24 * 3600)
            
    async def get_instance(self, instance_id: str) -> Optional[GoalInstance]:
        """Get goal instance from Redis."""
        key = f"goal:{instance_id}"
        data = await self.redis.hgetall(key)
        
        if not data:
            return None
            
        return GoalInstance.from_redis_hash(instance_id, data)
        
    async def get_instances_by_goal(self, goal_id: str) -> List[GoalInstance]:
        """Get all instances for a specific goal."""
        instance_ids = await self.redis.smembers(f"goal_instances:{goal_id}")
        
        instances = []
        for instance_id in instance_ids:
            instance = await self.get_instance(instance_id)
            if instance:
                instances.append(instance)
                
        return sorted(instances, key=lambda x: x.started_at or datetime.min, reverse=True)
        
    async def get_ready_instances(self, limit: int = 100) -> List[str]:
        """Get instance IDs ready to run (next_run_ts <= now)."""
        now = time.time()
        
        # Get instances with next_run_ts <= now
        results = await self.redis.zrangebyscore(
            "goal_queue", 
            min=0, 
            max=now,
            start=0,
            num=limit
        )
        
        return results
        
    async def update_instance_state(
        self, 
        instance_id: str, 
        state: GoalState,
        error: Optional[str] = None
    ) -> None:
        """Update instance state."""
        instance = await self.get_instance(instance_id)
        if not instance:
            logger.error(f"Instance {instance_id} not found")
            return
            
        instance.state = state
        if error:
            instance.last_error = error
            instance.fail_count += 1
            
        if state == GoalState.IN_PROGRESS:
            instance.started_at = datetime.utcnow()
        elif state in [GoalState.SUCCEEDED, GoalState.FAILED]:
            instance.completed_at = datetime.utcnow()
            
        await self.save_instance(instance)
        
    async def increment_step(self, instance_id: str, step_result: Dict[str, Any]) -> None:
        """Increment current step and save result."""
        instance = await self.get_instance(instance_id)
        if not instance:
            return
            
        # Save step result
        step_id = f"step_{instance.current_step}"
        instance.step_results[step_id] = step_result
        
        # Increment step
        instance.current_step += 1
        
        await self.save_instance(instance)
        
    async def get_all_goal_ids(self) -> Set[str]:
        """Get all unique goal IDs from instances."""
        # Scan for all goal_instances:* keys
        goal_ids = set()
        cursor = 0
        
        while True:
            cursor, keys = await self.redis.scan(
                cursor, 
                match="goal_instances:*",
                count=100
            )
            
            for key in keys:
                # Extract goal_id from key
                goal_id = key.replace("goal_instances:", "")
                goal_ids.add(goal_id)
                
            if cursor == 0:
                break
                
        return goal_ids
        
    async def cleanup_old_instances(self, days: int = 7) -> int:
        """Clean up old completed/failed instances."""
        # Redis expiration handles this automatically
        # This method is for manual cleanup if needed
        count = 0
        cursor = 0
        
        cutoff_time = time.time() - (days * 24 * 3600)
        
        while True:
            cursor, keys = await self.redis.scan(
                cursor,
                match="goal:*",
                count=100
            )
            
            for key in keys:
                instance_id = key.replace("goal:", "")
                instance = await self.get_instance(instance_id)
                
                if instance and instance.completed_at:
                    completed_ts = instance.completed_at.timestamp()
                    if completed_ts < cutoff_time:
                        await self.redis.delete(key)
                        await self.redis.srem(f"goal_instances:{instance.goal_id}", instance_id)
                        count += 1
                        
            if cursor == 0:
                break
                
        logger.info(f"Cleaned up {count} old goal instances")
        return count

