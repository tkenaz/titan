"""
Event logging for Model Gateway
"""
import json
import uuid
from datetime import datetime
from typing import Dict, Any, Optional
import redis.asyncio as redis
import logging

logger = logging.getLogger(__name__)


class EventLogger:
    """Log model gateway events to Redis streams"""
    
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self.stream_key = "agent.events"
    
    async def log_request(
        self,
        model: str,
        trace_id: str,
        request_size: int,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log model request start"""
        event = {
            "event_type": "model.request.start",
            "model": model,
            "trace_id": trace_id,
            "request_size": request_size,
            "timestamp": datetime.utcnow().isoformat(),
            "metadata": json.dumps(metadata or {})
        }
        
        await self._add_event(event)
    
    async def log_response(
        self,
        model: str,
        trace_id: str,
        tokens_in: int,
        tokens_out: int,
        cost_usd: float,
        latency_ms: float,
        status: str = "success",
        error: Optional[str] = None
    ) -> None:
        """Log model response completion"""
        event = {
            "event_type": "model.request.complete",
            "model": model,
            "trace_id": trace_id,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "usd": cost_usd,
            "latency_ms": latency_ms,
            "status": status,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        if error:
            event["error"] = error
        
        await self._add_event(event)
    
    async def log_budget_warning(
        self,
        budget_used_percent: float,
        daily_total: float,
        daily_limit: float
    ) -> None:
        """Log budget warning"""
        event = {
            "event_type": "model.budget.warning",
            "budget_used_percent": budget_used_percent,
            "daily_total": daily_total,
            "daily_limit": daily_limit,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        await self._add_event(event)
    
    async def log_budget_exceeded(
        self,
        daily_total: float,
        daily_limit: float,
        blocked_model: str
    ) -> None:
        """Log budget exceeded event"""
        event = {
            "event_type": "model.budget.exceeded",
            "daily_total": daily_total,
            "daily_limit": daily_limit,
            "blocked_model": blocked_model,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        await self._add_event(event)
    
    async def log_streaming_start(
        self,
        model: str,
        trace_id: str
    ) -> None:
        """Log streaming response start"""
        event = {
            "event_type": "model.streaming.start",
            "model": model,
            "trace_id": trace_id,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        await self._add_event(event)
    
    async def _add_event(self, event: Dict[str, Any]) -> None:
        """Add event to Redis stream"""
        try:
            # Convert all values to strings for Redis
            event_data = {
                k: str(v) for k, v in event.items()
            }
            
            await self.redis.xadd(
                self.stream_key,
                event_data,
                maxlen=100000  # Keep last 100k events
            )
        except Exception as e:
            logger.error(f"Failed to log event: {e}")
