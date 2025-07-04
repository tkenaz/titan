"""Cost tracking for embeddings and LLM calls."""

import logging
from datetime import datetime
from typing import Optional

import redis.asyncio as aioredis
from prometheus_client import Summary, Counter

logger = logging.getLogger(__name__)

# Pricing constants (USD per token)
PRICE_EMBED = 0.0001 / 1000  # text-embedding-3-small
PRICE_LLM = 0.0005 / 1000    # gpt-3.5-turbo (adjust as needed)

# Prometheus metrics
cost_usd_total = Summary(
    'titan_cost_usd_total',
    'Total USD spent on API calls',
    ['service', 'type']
)

api_tokens_total = Counter(
    'titan_api_tokens_total', 
    'Total tokens used in API calls',
    ['service', 'type']
)


class CostTracker:
    """Track costs for API usage."""
    
    def __init__(self, redis_url: str = "redis://localhost:6379/0"):
        self.redis_url = redis_url
        self._redis: Optional[aioredis.Redis] = None
        
    async def connect(self):
        """Connect to Redis."""
        if not self._redis:
            self._redis = await aioredis.from_url(
                self.redis_url,
                decode_responses=True
            )
            
    async def disconnect(self):
        """Disconnect from Redis."""
        if self._redis:
            await self._redis.close()
            
    async def add_cost(
        self, 
        kind: str, 
        tokens: int,
        service: str = "memory"
    ):
        """Add cost for API usage.
        
        Args:
            kind: Type of usage ('embed' or 'llm')
            tokens: Number of tokens used
            service: Service name for tracking
        """
        if not self._redis:
            await self.connect()
            
        # Calculate cost
        price = PRICE_EMBED if kind == "embed" else PRICE_LLM
        usd = tokens * price
        
        # Store in Redis (daily aggregation)
        key = f"cost:{datetime.utcnow():%Y%m%d}"
        
        try:
            # Increment counters
            await self._redis.hincrbyfloat(key, "usd_total", usd)
            await self._redis.hincrby(key, f"{kind}_tokens", tokens)
            
            # Set expiry (keep for 90 days)
            await self._redis.expire(key, 90 * 24 * 3600)
            
            # Update Prometheus metrics
            cost_usd_total.labels(service=service, type=kind).observe(usd)
            api_tokens_total.labels(service=service, type=kind).inc(tokens)
            
            logger.debug(f"Added cost: {kind} {tokens} tokens = ${usd:.6f}")
            
        except Exception as e:
            logger.error(f"Failed to track cost: {e}")
            
    async def get_daily_cost(self, date: Optional[datetime] = None) -> dict:
        """Get cost for a specific day.
        
        Args:
            date: Date to query (default: today)
            
        Returns:
            Dict with cost breakdown
        """
        if not self._redis:
            await self.connect()
            
        if date is None:
            date = datetime.utcnow()
            
        key = f"cost:{date:%Y%m%d}"
        
        try:
            data = await self._redis.hgetall(key)
            
            return {
                "date": date.strftime("%Y-%m-%d"),
                "usd_total": float(data.get("usd_total", 0)),
                "embed_tokens": int(data.get("embed_tokens", 0)),
                "llm_tokens": int(data.get("llm_tokens", 0))
            }
            
        except Exception as e:
            logger.error(f"Failed to get daily cost: {e}")
            return {
                "date": date.strftime("%Y-%m-%d"),
                "usd_total": 0.0,
                "embed_tokens": 0,
                "llm_tokens": 0
            }
            
    async def get_monthly_cost(self, year: int, month: int) -> dict:
        """Get aggregated cost for a month.
        
        Args:
            year: Year
            month: Month (1-12)
            
        Returns:
            Dict with monthly cost breakdown
        """
        if not self._redis:
            await self.connect()
            
        total_usd = 0.0
        total_embed = 0
        total_llm = 0
        
        # Iterate through days in month
        from calendar import monthrange
        days_in_month = monthrange(year, month)[1]
        
        for day in range(1, days_in_month + 1):
            date = datetime(year, month, day)
            daily = await self.get_daily_cost(date)
            
            total_usd += daily["usd_total"]
            total_embed += daily["embed_tokens"]
            total_llm += daily["llm_tokens"]
            
        return {
            "year": year,
            "month": month,
            "usd_total": total_usd,
            "embed_tokens": total_embed,
            "llm_tokens": total_llm
        }


# Global instance
_cost_tracker: Optional[CostTracker] = None


async def get_cost_tracker() -> CostTracker:
    """Get or create global cost tracker."""
    global _cost_tracker
    
    if not _cost_tracker:
        _cost_tracker = CostTracker()
        await _cost_tracker.connect()
        
    return _cost_tracker
