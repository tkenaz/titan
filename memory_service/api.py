"""FastAPI application for Memory Service."""

import logging
from contextlib import asynccontextmanager
from typing import List

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import Counter, Histogram, Gauge
import time

from memory_service.config import MemoryConfig
from memory_service.service import MemoryService
from memory_service.event_integration import MemoryEventBusIntegration
from memory_service.models import (
    EvaluationRequest,
    EvaluationResponse,
    SearchRequest,
    MemorySearchResult,
    RememberRequest,
    ForgetRequest,
)


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Prometheus metrics
memory_eval_latency = Histogram(
    "titan_memory_eval_latency_ms",
    "Memory evaluation latency in milliseconds"
)
memory_saved_total = Counter(
    "titan_memory_saved_total",
    "Total memories saved"
)
memory_deleted_total = Counter(
    "titan_memory_deleted_total",
    "Total memories deleted"
)
memory_gc_duration = Histogram(
    "titan_memory_gc_duration_ms",
    "Garbage collection duration in milliseconds"
)
memory_vector_queries = Counter(
    "titan_memory_vector_queries_total",
    "Total vector similarity queries"
)

# Global memory service instance
memory_service: MemoryService = None
event_integration: MemoryEventBusIntegration = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    global memory_service
    
    # Load config
    config = MemoryConfig()
    try:
        # Try to load from YAML if available
        import os
        config_path = os.getenv("MEMORY_CONFIG_PATH", "/app/config/memory.yaml")
        if os.path.exists(config_path):
            config = MemoryConfig.from_yaml(config_path)
            logger.info(f"Loaded config from {config_path}")
    except Exception as e:
        logger.warning(f"Failed to load config file: {e}, using defaults")
    
    # Initialize service
    memory_service = MemoryService(config)
    await memory_service.connect()
    logger.info("Memory Service started")
    
    # Initialize Event Bus integration
    event_integration = MemoryEventBusIntegration(config, memory_service)
    try:
        await event_integration.start()
        logger.info("Event Bus integration started")
    except Exception as e:
        logger.warning(f"Event Bus integration failed to start: {e}")
        # Continue without event integration
    
    yield
    
    # Cleanup
    if event_integration:
        await event_integration.stop()
    await memory_service.disconnect()
    logger.info("Memory Service stopped")


# Create FastAPI app
app = FastAPI(
    title="Titan Memory Service",
    description="Long-term and short-term memory for Titan",
    version="0.1.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "memory"}


@app.post("/memory/evaluate", response_model=EvaluationResponse)
async def evaluate_message(request: EvaluationRequest):
    """Evaluate and potentially save a message to memory."""
    start_time = time.time()
    
    try:
        response = await memory_service.evaluate_and_save(request)
        
        # Update metrics
        if response.saved:
            memory_saved_total.inc()
        
        return response
        
    except Exception as e:
        logger.error(f"Evaluation error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
    finally:
        # Record latency
        latency_ms = (time.time() - start_time) * 1000
        memory_eval_latency.observe(latency_ms)


@app.get("/memory/search", response_model=List[MemorySearchResult])
async def search_memories(
    q: str,
    k: int = 10,
    tags: List[str] = None,
    min_similarity: float = 0.5
):
    """Search for memories."""
    memory_vector_queries.inc()
    
    try:
        request = SearchRequest(
            query=q,
            k=k,
            tags=tags,
            min_similarity=min_similarity
        )
        
        results = await memory_service.search(request)
        return results
        
    except Exception as e:
        logger.error(f"Search error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@app.post("/memory/remember")
async def remember_explicitly(request: RememberRequest):
    """Explicitly remember something."""
    try:
        memory_id = await memory_service.remember(request)
        memory_saved_total.inc()
        
        return {"id": memory_id, "status": "remembered"}
        
    except Exception as e:
        logger.error(f"Remember error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@app.post("/memory/forget")
async def forget_memory(request: ForgetRequest):
    """Forget a specific memory."""
    try:
        deleted = await memory_service.forget(request)
        
        if deleted:
            memory_deleted_total.inc()
            return {"deleted": True, "id": request.id}
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Memory {request.id} not found"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Forget error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@app.post("/memory/gc")
async def run_garbage_collection():
    """Manually trigger garbage collection."""
    start_time = time.time()
    
    try:
        deleted_ids = await memory_service.garbage_collect()
        
        # Update metrics
        for _ in deleted_ids:
            memory_deleted_total.inc()
        
        duration_ms = (time.time() - start_time) * 1000
        memory_gc_duration.observe(duration_ms)
        
        return {
            "deleted_count": len(deleted_ids),
            "deleted_ids": deleted_ids,
            "duration_ms": duration_ms
        }
        
    except Exception as e:
        logger.error(f"GC error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# Prometheus metrics endpoint
from prometheus_client import make_asgi_app
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
