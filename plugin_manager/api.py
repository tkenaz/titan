"""Plugin Manager API with authentication."""

import os
from contextlib import asynccontextmanager
from typing import Optional
from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from plugin_manager.enhanced_manager import EnhancedPluginManager

# Global manager instance
manager: Optional[EnhancedPluginManager] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan."""
    global manager
    
    # Startup
    manager = EnhancedPluginManager(
        plugin_dir=os.getenv("PLUGIN_DIR", "./plugins"),
        redis_url=os.getenv("REDIS_URL", "redis://localhost:6379/0")
    )
    
    await manager.initialize()
    
    yield
    
    # Shutdown
    if manager:
        await manager.shutdown()


# Initialize FastAPI app
app = FastAPI(
    title="Titan Plugin Manager API",
    version="1.0.0",
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

# Security
security = HTTPBearer()


class PluginExecuteRequest(BaseModel):
    """Request to execute a plugin."""
    plugin: str
    event_data: dict


class PluginPauseRequest(BaseModel):
    """Request to pause a plugin."""
    minutes: int = 60


class CleanupRequest(BaseModel):
    """Request to cleanup containers."""
    force: bool = False


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



@app.get("/health")
async def health():
    """Health check endpoint (no auth required)."""
    return {"status": "healthy", "service": "plugin-manager"}


@app.get("/plugins", dependencies=[Depends(verify_token)])
async def list_plugins():
    """List all plugins and their status."""
    if not manager:
        raise HTTPException(status_code=503, detail="Manager not initialized")
    
    return await manager.get_plugin_status()


@app.get("/plugins/{plugin_name}", dependencies=[Depends(verify_token)])
async def get_plugin_status(plugin_name: str):
    """Get detailed status of a specific plugin."""
    if not manager:
        raise HTTPException(status_code=503, detail="Manager not initialized")
    
    status = await manager.get_plugin_status()
    plugin_status = status['plugins'].get(plugin_name)
    
    if not plugin_status:
        raise HTTPException(status_code=404, detail=f"Plugin {plugin_name} not found")
    
    # Get health details
    health = await manager.circuit_breaker.get_plugin_health(plugin_name)
    
    return {
        "plugin": plugin_name,
        "status": plugin_status,
        "health": {
            "state": health.state.value if health else "unknown",
            "consecutive_failures": health.consecutive_failures if health else 0,
            "failure_reasons": health.failure_reasons[-5:] if health else []  # Last 5 failures
        }
    }


@app.post("/plugins/{plugin_name}/execute", dependencies=[Depends(verify_token)])
async def execute_plugin(plugin_name: str, request: PluginExecuteRequest):
    """Execute a plugin manually."""
    if not manager:
        raise HTTPException(status_code=503, detail="Manager not initialized")
    
    if request.plugin != plugin_name:
        raise HTTPException(
            status_code=400,
            detail="Plugin name in URL and body must match"
        )
    
    result = await manager.execute_plugin(plugin_name, request.event_data)
    
    if not result['success']:
        raise HTTPException(
            status_code=500,
            detail=result.get('error', 'Plugin execution failed')
        )
    
    return result


@app.post("/plugins/{plugin_name}/reset", dependencies=[Depends(verify_token)])
async def reset_plugin(plugin_name: str):
    """Reset a plugin to healthy state."""
    if not manager:
        raise HTTPException(status_code=503, detail="Manager not initialized")
    
    success = await manager.reset_plugin(plugin_name)
    
    if not success:
        raise HTTPException(status_code=404, detail=f"Plugin {plugin_name} not found")
    
    return {"message": f"Plugin {plugin_name} reset to healthy state"}


@app.post("/plugins/{plugin_name}/pause", dependencies=[Depends(verify_token)])
async def pause_plugin(plugin_name: str, request: PluginPauseRequest):
    """Pause a plugin for specified minutes."""
    if not manager:
        raise HTTPException(status_code=503, detail="Manager not initialized")
    
    success = await manager.pause_plugin(plugin_name, request.minutes)
    
    if not success:
        raise HTTPException(status_code=404, detail=f"Plugin {plugin_name} not found")
    
    return {
        "message": f"Plugin {plugin_name} paused for {request.minutes} minutes"
    }


@app.post("/containers/cleanup", dependencies=[Depends(verify_token)])
async def cleanup_containers(request: CleanupRequest):
    """Cleanup Docker containers."""
    if not manager:
        raise HTTPException(status_code=503, detail="Manager not initialized")
    
    cleaned = await manager.cleanup_containers(force=request.force)
    
    return {
        "cleaned": cleaned,
        "force": request.force
    }


@app.get("/containers/stats", dependencies=[Depends(verify_token)])
async def container_stats():
    """Get container statistics."""
    if not manager:
        raise HTTPException(status_code=503, detail="Manager not initialized")
    
    if not manager.watchdog:
        raise HTTPException(status_code=503, detail="Watchdog not initialized")
    
    return await manager.watchdog.get_container_stats()


# Metrics endpoint (Prometheus format)
@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint (no auth for scraping)."""
    from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
    from fastapi.responses import Response
    
    return Response(
        generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )


if __name__ == "__main__":
    import uvicorn
    
    # Load from environment
    host = os.getenv("PLUGIN_API_HOST", "0.0.0.0")
    port = int(os.getenv("PLUGIN_API_PORT", "8003"))
    
    uvicorn.run(app, host=host, port=port)
