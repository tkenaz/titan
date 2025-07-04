"""
Cost tracking and budget management
"""
import redis.asyncio as redis
from typing import Dict, Optional, Tuple, Any
from datetime import datetime
import json
import logging

logger = logging.getLogger(__name__)


class CostTracker:
    """Track costs and enforce budget limits"""
    
    def __init__(self, redis_client: redis.Redis, daily_limit_usd: float = 20.0):
        self.redis = redis_client
        self.daily_limit_usd = daily_limit_usd
        self.key_prefix = "titan:cost"
    
    def _get_date_key(self) -> str:
        """Get Redis key for today's costs"""
        return f"{self.key_prefix}:{datetime.now().strftime('%Y%m%d')}"
    
    async def add_cost(
        self,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        input_cost_per_token: float,
        output_cost_per_token: float,
        trace_id: str
    ) -> Dict[str, float]:
        """
        Add cost to tracker
        Returns: dict with cost breakdown
        """
        # Calculate costs
        input_cost = prompt_tokens * input_cost_per_token
        output_cost = completion_tokens * output_cost_per_token
        total_cost = input_cost + output_cost
        
        # Update Redis atomically
        date_key = self._get_date_key()
        pipe = self.redis.pipeline()
        
        # Increment total daily cost
        pipe.hincrbyfloat(date_key, "total", total_cost)
        pipe.hincrbyfloat(date_key, f"model:{model}", total_cost)
        pipe.hincrbyfloat(date_key, "prompt_tokens", prompt_tokens)
        pipe.hincrbyfloat(date_key, "completion_tokens", completion_tokens)
        
        # Set expiry (7 days)
        pipe.expire(date_key, 7 * 24 * 3600)
        
        # Store detailed record
        record = {
            "timestamp": datetime.utcnow().isoformat(),
            "model": model,
            "trace_id": trace_id,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "input_cost": input_cost,
            "output_cost": output_cost,
            "total_cost": total_cost
        }
        pipe.xadd(
            f"{self.key_prefix}:stream",
            {"data": json.dumps(record)},
            maxlen=10000  # Keep last 10k records
        )
        
        results = await pipe.execute()
        current_total = float(results[0])
        
        return {
            "input_cost": input_cost,
            "output_cost": output_cost,
            "total_cost": total_cost,
            "daily_total": current_total,
            "daily_limit": self.daily_limit_usd,
            "budget_remaining": self.daily_limit_usd - current_total
        }
    
    async def check_budget(self) -> Tuple[bool, Dict[str, float]]:
        """
        Check if budget allows new requests
        Returns: (is_allowed, stats)
        """
        date_key = self._get_date_key()
        current_total = await self.redis.hget(date_key, "total")
        current_total = float(current_total or 0)
        
        stats = {
            "daily_total": current_total,
            "daily_limit": self.daily_limit_usd,
            "budget_remaining": self.daily_limit_usd - current_total,
            "budget_used_percent": (current_total / self.daily_limit_usd * 100) if self.daily_limit_usd > 0 else 0
        }
        
        is_allowed = current_total < self.daily_limit_usd
        return is_allowed, stats
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get detailed cost statistics"""
        date_key = self._get_date_key()
        data = await self.redis.hgetall(date_key)
        
        if not data:
            return {
                "daily_total": 0.0,
                "models": {},
                "tokens": {"prompt": 0, "completion": 0}
            }
        
        # Parse stats
        stats = {
            "daily_total": float(data.get(b"total", 0)),
            "models": {},
            "tokens": {
                "prompt": int(float(data.get(b"prompt_tokens", 0))),
                "completion": int(float(data.get(b"completion_tokens", 0)))
            }
        }
        
        # Extract per-model costs
        for key, value in data.items():
            key_str = key.decode()
            if key_str.startswith("model:"):
                model_name = key_str.split(":", 1)[1]
                stats["models"][model_name] = float(value)
        
        return stats
    
    async def reset_daily_budget(self) -> None:
        """Reset daily budget (admin function)"""
        date_key = self._get_date_key()
        await self.redis.delete(date_key)
        logger.info(f"Reset daily budget for {date_key}")


class BudgetGuard:
    """Guard against budget overruns"""
    
    def __init__(
        self,
        cost_tracker: CostTracker,
        hard_stop: bool = True,
        warning_threshold: float = 0.8
    ):
        self.cost_tracker = cost_tracker
        self.hard_stop = hard_stop
        self.warning_threshold = warning_threshold
    
    async def check_request_allowed(self) -> Tuple[bool, Optional[str], Dict[str, Any]]:
        """
        Check if request should be allowed
        Returns: (allowed, reason, stats)
        """
        is_allowed, stats = await self.cost_tracker.check_budget()
        
        if not is_allowed and self.hard_stop:
            return False, "Daily budget exceeded", stats
        
        # Check warning threshold
        if stats["budget_used_percent"] >= self.warning_threshold * 100:
            stats["warning"] = f"Budget usage at {stats['budget_used_percent']:.1f}%"
        
        return True, None, stats
