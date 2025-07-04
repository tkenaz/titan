"""Memory Service API with authentication."""

import os
from contextlib import asynccontextmanager
from typing import List, Optional
from fastapi import FastAPI, HTTPException, Query, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import JSONResponse
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

from memory_service.service import MemoryService
from memory_service.config import MemoryConfig
from memory_service.models import (
    EvaluationRequest,
    EvaluationResponse,
    SearchRequest,
    RememberRequest,
    ForgetRequest,
    MemorySearchResult
)

# Global service instance
memory_service: Optional[MemoryService] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan."""
    global memory_service
    
    # Startup
    config_path = os.getenv("MEMORY_CONFIG_PATH", "config/memory.yaml")
    
    # Use local config if running outside docker
    if not os.path.exists("/.dockerenv"):  # Not in docker
        config_path = "config/memory-local.yaml"
    
    if os.path.exists(config_path):
        config = MemoryConfig.from_yaml(config_path)
    else:
        config = MemoryConfig()
    
    # Initialize service
    memory_service = MemoryService(config)
    await memory_service.connect()
    
    yield
    
    # Shutdown
    if memory_service:
        await memory_service.disconnect()


# Initialize FastAPI app with lifespan
app = FastAPI(
    title="Titan Memory Service API",
    version="1.0.0",
    lifespan=lifespan
)

# Security
security = HTTPBearer()


async def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """Verify Bearer token."""
    token = credentials.credentials
    expected_token = os.getenv("ADMIN_TOKEN", "")
    
    if not expected_token:
        raise HTTPException(
            status_code=500,
            detail="ADMIN_TOKEN not configured"
        )
    
    if token != expected_token:
        raise HTTPException(
            status_code=401,
            detail="Invalid authentication token"
        )
    
    return token


# Health check (no auth)
@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy", "service": "memory-service"}


# Metrics endpoint (no auth for Prometheus)
@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    return JSONResponse(
        content=generate_latest().decode('utf-8'),
        media_type=CONTENT_TYPE_LATEST
    )


# Protected endpoints
@app.post("/memory/evaluate", dependencies=[Depends(verify_token)])
async def evaluate_message(request: EvaluationRequest) -> EvaluationResponse:
    """Evaluate if a message should be saved to memory."""
    if not memory_service:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    return await memory_service.evaluate_and_save(request)


@app.post("/memory/search", dependencies=[Depends(verify_token)])
async def search_memories(request: SearchRequest) -> List[MemorySearchResult]:
    """Search memories."""
    if not memory_service:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    # Include similarity scores in response
    results = await memory_service.search(request)
    
    # Enhance results with scores for API
    for result in results:
        # Add score field for backward compatibility
        result.score = result.similarity
    
    return results


@app.post("/memory/remember", dependencies=[Depends(verify_token)])
async def remember(request: RememberRequest) -> dict:
    """Explicitly remember something."""
    if not memory_service:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    memory_id = await memory_service.remember(request)
    
    return {
        "id": memory_id,
        "message": "Memory saved successfully"
    }


@app.delete("/memory/{memory_id}", dependencies=[Depends(verify_token)])
async def forget(memory_id: str, reason: Optional[str] = Query(None)):
    """Forget a specific memory."""
    if not memory_service:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    request = ForgetRequest(id=memory_id, reason=reason)
    deleted = await memory_service.forget(request)
    
    if not deleted:
        raise HTTPException(status_code=404, detail="Memory not found")
    
    return {"message": f"Memory {memory_id} deleted"}


@app.post("/memory/gc", dependencies=[Depends(verify_token)])
async def garbage_collect():
    """Run garbage collection."""
    if not memory_service:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    deleted_ids = await memory_service.garbage_collect()
    
    return {
        "deleted_count": len(deleted_ids),
        "deleted_ids": deleted_ids
    }


@app.get("/memory/stats", dependencies=[Depends(verify_token)])
async def memory_stats():
    """Get memory statistics."""
    if not memory_service:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    # Get count from database
    async with memory_service.vector_storage._pool.acquire() as conn:
        count_result = await conn.fetchval("SELECT COUNT(*) FROM memory_entries")
        
        # Get stats by priority
        priority_stats = await conn.fetch("""
            SELECT static_priority, COUNT(*) as count 
            FROM memory_entries 
            GROUP BY static_priority
        """)
        
        # Get recent activity
        recent_stats = await conn.fetchrow("""
            SELECT 
                COUNT(*) FILTER (WHERE created_at > NOW() - INTERVAL '1 hour') as last_hour,
                COUNT(*) FILTER (WHERE created_at > NOW() - INTERVAL '24 hours') as last_day,
                COUNT(*) FILTER (WHERE created_at > NOW() - INTERVAL '7 days') as last_week
            FROM memory_entries
        """)
    
    return {
        "total_memories": count_result,
        "by_priority": {row['static_priority']: row['count'] for row in priority_stats},
        "recent_activity": {
            "last_hour": recent_stats['last_hour'],
            "last_day": recent_stats['last_day'],
            "last_week": recent_stats['last_week']
        }
    }


@app.get("/memory/cost", dependencies=[Depends(verify_token)])
async def get_cost_stats(days: int = Query(7, ge=1, le=90)):
    """Get cost statistics for the last N days."""
    from memory_service.cost import get_cost_tracker
    from datetime import datetime, timedelta
    
    cost_tracker = await get_cost_tracker()
    
    total_usd = 0.0
    total_embed = 0
    total_llm = 0
    daily_costs = []
    
    # Get costs for last N days
    for i in range(days):
        date = datetime.utcnow() - timedelta(days=i)
        daily = await cost_tracker.get_daily_cost(date)
        
        if daily["usd_total"] > 0 or i == 0:  # Include today even if zero
            daily_costs.append(daily)
            total_usd += daily["usd_total"]
            total_embed += daily["embed_tokens"]
            total_llm += daily["llm_tokens"]
    
    return {
        "period_days": days,
        "total_usd": round(total_usd, 6),
        "total_embed_tokens": total_embed,
        "total_llm_tokens": total_llm,
        "daily_breakdown": daily_costs
    }


# Special endpoint for testing without auth (development only)
if os.getenv("ENVIRONMENT") == "development":
    @app.get("/memory/search")
    async def search_memories_dev(
        q: str = Query(..., description="Search query"),
        k: int = Query(10, description="Number of results")
    ):
        """Development search endpoint without auth."""
        if not memory_service:
            raise HTTPException(status_code=503, detail="Service not initialized")
        
        request = SearchRequest(query=q, k=k)
        return await memory_service.search(request)


if __name__ == "__main__":
    import uvicorn
    
    # Load from environment
    host = os.getenv("MEMORY_API_HOST", "0.0.0.0")
    port = int(os.getenv("MEMORY_API_PORT", "8001"))
    
    uvicorn.run(app, host=host, port=port)
