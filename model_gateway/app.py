"""
Model Gateway FastAPI Application
"""
import os
from pathlib import Path
from typing import Dict, Any, Optional, List
from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI, HTTPException, Header, Depends, Request
from fastapi.responses import StreamingResponse, PlainTextResponse
from pydantic import BaseModel, Field
import redis.asyncio as redis
import json
from prometheus_client import Counter, Histogram, Gauge, generate_latest
import time

from .config import GatewayConfig
from .cost_tracker import CostTracker
from .events import EventLogger
from .router import ModelRouter
from .insights import ModelInsights

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global instances
redis_client: Optional[redis.Redis] = None
model_router: Optional[ModelRouter] = None
gateway_config: Optional[GatewayConfig] = None
model_insights: Optional[ModelInsights] = None

# Prometheus metrics
request_counter = Counter(
    'titan_model_requests_total',
    'Total number of model requests',
    ['model', 'status']
)

latency_histogram = Histogram(
    'titan_model_latency_seconds',
    'Model request latency',
    ['model']
)

cost_gauge = Gauge(
    'titan_cost_usd_total',
    'Total cost in USD'
)

budget_exceeded_counter = Counter(
    'titan_budget_exceeded_total',
    'Number of times budget was exceeded'
)


class ProxyRequest(BaseModel):
    """OpenAI-compatible request format"""
    model: Optional[str] = None  # Made optional since we get it from URL
    messages: List[Dict[str, str]]
    temperature: float = 0.7
    max_tokens: Optional[int] = None
    stream: bool = False
    # Additional OpenAI parameters
    top_p: Optional[float] = None
    frequency_penalty: Optional[float] = None
    presence_penalty: Optional[float] = None
    

class ProxyResponse(BaseModel):
    """Response format for non-streaming requests"""
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: List[Dict[str, Any]]
    usage: Dict[str, int]
    # Additional metadata
    cost: Optional[Dict[str, float]] = None
    signature: Optional[str] = None
    

class ModelInfo(BaseModel):
    """Model information"""
    name: str
    provider: str
    input_cost: float = Field(description="USD per input token")
    output_cost: float = Field(description="USD per output token")
    max_tokens: int
    supports_streaming: bool = True
    

class ModelsResponse(BaseModel):
    """List of available models"""
    models: List[ModelInfo]
    defaults: Dict[str, str]
    budget: Dict[str, Any]


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    global redis_client, model_router, gateway_config, model_insights
    
    # Startup
    logger.info("Starting Model Gateway...")
    
    # Load configuration
    config_path = Path("config/models.yaml")
    if not config_path.exists():
        # Create default config if not exists
        config_path.parent.mkdir(exist_ok=True)
        with open(config_path, 'w') as f:
            f.write(DEFAULT_CONFIG)
    
    gateway_config = GatewayConfig.from_yaml(config_path)
    
    # Initialize Redis
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
    redis_client = await redis.from_url(redis_url)
    
    # Initialize components
    cost_tracker = CostTracker(
        redis_client=redis_client,
        daily_limit_usd=gateway_config.budget.daily_limit_usd
    )
    event_logger = EventLogger(redis_client)
    
    # Initialize insights if DB_URL is available
    db_url = os.getenv("DB_URL")
    if db_url:
        try:
            model_insights = ModelInsights(db_url)
            await model_insights.initialize()
            logger.info("Model insights initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize insights: {e}")
            model_insights = None
    
    # Initialize router
    hmac_secret = os.getenv("HMAC_SECRET", "change-me-in-production")
    model_router = ModelRouter(
        config=gateway_config,
        cost_tracker=cost_tracker,
        event_logger=event_logger,
        hmac_secret=hmac_secret,
        insights=model_insights
    )
    
    logger.info(f"Model Gateway ready with {len(gateway_config.models)} models")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Model Gateway...")
    if model_insights:
        await model_insights.close()
    await redis_client.close()


# Create FastAPI app
app = FastAPI(
    title="Titan Model Gateway",
    version="0.2.0",
    lifespan=lifespan
)


async def verify_token(authorization: Optional[str] = Header(None)) -> str:
    """Verify Bearer token"""
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing authorization header")
    
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization format")
    
    token = authorization.split(" ", 1)[1]
    expected_token = os.getenv("ADMIN_TOKEN", "development-token")
    
    if token != expected_token:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    return token


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "model-gateway"}


@app.get("/metrics", response_class=PlainTextResponse)
async def metrics():
    """Prometheus metrics endpoint"""
    # Update cost gauge from Redis
    if redis_client and gateway_config:
        cost_tracker = CostTracker(redis_client, gateway_config.budget.daily_limit_usd)
        stats = await cost_tracker.get_stats()
        cost_gauge.set(stats["daily_total"])
    
    return generate_latest()


@app.get("/models", response_model=ModelsResponse)
async def list_models():
    """List available models with pricing"""
    models = []
    for name, config in gateway_config.models.items():
        models.append(ModelInfo(
            name=name,
            provider=config.provider,
            input_cost=config.input_cost,
            output_cost=config.output_cost,
            max_tokens=config.max_tokens,
            supports_streaming=config.supports_streaming
        ))
    
    # Get current budget stats
    cost_tracker = CostTracker(redis_client, gateway_config.budget.daily_limit_usd)
    budget_stats = await cost_tracker.get_stats()
    
    return ModelsResponse(
        models=models,
        defaults=gateway_config.defaults.dict(),
        budget={
            "daily_limit_usd": gateway_config.budget.daily_limit_usd,
            "daily_spent_usd": budget_stats["daily_total"],
            "remaining_usd": gateway_config.budget.daily_limit_usd - budget_stats["daily_total"],
            "models_usage": budget_stats["models"]
        }
    )


@app.post("/proxy/{model_name}")
async def proxy_request(
    model_name: str,
    request: ProxyRequest,
    authorization: str = Depends(verify_token)
):
    """Proxy request to model provider"""
    # Override model from path
    request.model = model_name
    
    if request.stream:
        # Return streaming response
        async def generate():
            """Generate streaming response"""
            try:
                async for chunk in model_router.stream_completion(
                    model_name=model_name,
                    messages=request.messages,
                    temperature=request.temperature,
                    max_tokens=request.max_tokens,
                    top_p=request.top_p,
                    frequency_penalty=request.frequency_penalty,
                    presence_penalty=request.presence_penalty
                ):
                    # Format as SSE
                    if "error" in chunk:
                        data = json.dumps(chunk)
                        yield f"data: {data}\n\n"
                        break
                    elif chunk.get("done"):
                        # Send final data
                        data = json.dumps(chunk)
                        yield f"data: {data}\n\n"
                        yield "data: [DONE]\n\n"
                    else:
                        # Send chunk
                        import time as time_module
                        openai_chunk = {
                            "id": chunk.get("trace_id", ""),
                            "object": "chat.completion.chunk",
                            "created": int(time_module.time()),
                            "model": model_name,
                            "choices": [{
                                "index": 0,
                                "delta": {"content": chunk["chunk"]},
                                "finish_reason": None
                            }],
                            "x_signature": chunk["signature"],
                            "x_seq": chunk["seq"]
                        }
                        data = json.dumps(openai_chunk)
                        yield f"data: {data}\n\n"
            except Exception as e:
                error_data = json.dumps({"error": str(e)})
                yield f"data: {error_data}\n\n"
        
        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no"  # Disable nginx buffering
            }
        )
    
    else:
        # Non-streaming request
        result = await model_router.route_completion(
            model_name=model_name,
            messages=request.messages,
            stream=False,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            top_p=request.top_p,
            frequency_penalty=request.frequency_penalty,
            presence_penalty=request.presence_penalty
        )
        
        # Check for errors
        if "error" in result:
            request_counter.labels(model=model_name, status="error").inc()
            if result.get("status") == 429:
                budget_exceeded_counter.inc()
            raise HTTPException(
                status_code=result.get("status", 500),
                detail=result["error"]
            )
        
        # Record metrics
        request_counter.labels(model=model_name, status="success").inc()
        latency_histogram.labels(model=model_name).observe(result["latency_ms"] / 1000.0)
        
        # Format OpenAI-compatible response
        response = ProxyResponse(
            id=result["trace_id"],
            created=int(time.time()),
            model=model_name,
            choices=[{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": result["content"]
                },
                "finish_reason": "stop"
            }],
            usage=result["usage"],
            cost=result["cost"],
            signature=result["signature"]
        )
        
        # Add signature header
        return response


@app.get("/insights/stats", dependencies=[Depends(verify_token)])
async def get_insights_stats(model: Optional[str] = None, hours: int = 24):
    """Get model performance statistics"""
    if not model_insights:
        raise HTTPException(status_code=503, detail="Insights not available")
    
    stats = await model_insights.get_model_stats(model=model, hours=hours)
    return stats


@app.get("/insights/trends", dependencies=[Depends(verify_token)])
async def get_cost_trends(days: int = 7, model: Optional[str] = None):
    """Get cost trends over time"""
    if not model_insights:
        raise HTTPException(status_code=503, detail="Insights not available")
    
    trends = await model_insights.get_cost_trends(days=days, model=model)
    return {"trends": trends}


@app.get("/insights/similar", dependencies=[Depends(verify_token)])
async def find_similar_requests(
    query: str,
    model: Optional[str] = None,
    limit: int = 10
):
    """Find similar previous requests"""
    if not model_insights:
        raise HTTPException(status_code=503, detail="Insights not available")
    
    similar = await model_insights.find_similar_requests(
        query=query,
        model=model,
        limit=limit
    )
    return {"similar_requests": similar}


@app.post("/insights/aggregate", dependencies=[Depends(verify_token)])
async def run_aggregation():
    """Manually trigger daily aggregation"""
    if not model_insights:
        raise HTTPException(status_code=503, detail="Insights not available")
    
    try:
        await model_insights.run_daily_aggregation()
        return {"message": "Aggregation completed successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/budget/reset", dependencies=[Depends(verify_token)])
async def reset_budget():
    """Reset daily budget (admin only)"""
    cost_tracker = CostTracker(redis_client, gateway_config.budget.daily_limit_usd)
    await cost_tracker.reset_daily_budget()
    return {"message": "Budget reset successfully"}


@app.get("/budget/stats", dependencies=[Depends(verify_token)])
async def get_budget_stats():
    """Get detailed budget statistics"""
    cost_tracker = CostTracker(redis_client, gateway_config.budget.daily_limit_usd)
    stats = await cost_tracker.get_stats()
    
    return {
        "daily_limit_usd": gateway_config.budget.daily_limit_usd,
        "daily_spent_usd": stats["daily_total"],
        "remaining_usd": gateway_config.budget.daily_limit_usd - stats["daily_total"],
        "models_usage": stats["models"],
        "tokens": stats["tokens"]
    }


# Default configuration template
DEFAULT_CONFIG = """models:
  o3-pro:
    provider: openai
    engine: o3-pro
    input_cost: 0.00002   # USD per token
    output_cost: 0.00008
    max_tokens: 4096
  gpt-4o:
    provider: openai
    engine: gpt-4o
    input_cost: 0.0000025
    output_cost: 0.00001
    max_tokens: 8192
  gpt-4.5-preview:
    provider: openai
    engine: gpt-4.5-preview
    input_cost: 0.000075
    output_cost: 0.00015
    max_tokens: 32768

defaults:
  self_reflection: o3-pro
  self_reflection_frequent: gpt-4o
  vitals: gpt-4o
  experiment: o3-pro

budget:
  daily_limit_usd: 20
  hard_stop: true
  warning_threshold: 0.8
"""


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8081)
