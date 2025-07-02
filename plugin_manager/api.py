"""FastAPI application for Plugin Manager."""

import logging
from typing import Dict, List, Optional
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from plugin_manager.manager import PluginManager
from plugin_manager.config import PluginManagerConfig
from plugin_manager.event_bus import PluginEventBusIntegration


logger = logging.getLogger(__name__)

# API models
class PluginListResponse(BaseModel):
    plugins: Dict[str, Dict]


class TriggerRequest(BaseModel):
    plugin_name: str
    event_data: Dict


class TriggerResponse(BaseModel):
    success: bool
    stdout: Optional[str] = None
    stderr: Optional[str] = None
    error: Optional[str] = None
    duration_ms: float


# Create FastAPI app
app = FastAPI(
    title="Titan Plugin Manager",
    description="Dynamic plugin management for Titan",
    version="0.1.0"
)

# Global instances (initialized in lifespan)
plugin_manager: Optional[PluginManager] = None
event_bus: Optional[PluginEventBusIntegration] = None


@app.on_event("startup")
async def startup():
    """Initialize plugin manager on startup."""
    global plugin_manager, event_bus
    
    # Load config
    config_path = Path("config/plugins-local.yaml")
    if not config_path.exists():
        config_path = Path("config/plugins.yaml")
    
    if config_path.exists():
        config = PluginManagerConfig.from_yaml(str(config_path))
    else:
        config = PluginManagerConfig()
    
    # Create plugin manager
    plugin_manager = PluginManager(config)
    await plugin_manager.start()
    
    # Create event bus integration (optional for local testing)
    try:
        event_bus = PluginEventBusIntegration(config, plugin_manager)
        await event_bus.start()
    except Exception as e:
        logger.warning(f"Event Bus integration failed: {e}")
        logger.warning("Running without Event Bus integration")
    
    logger.info("Plugin Manager API started")


@app.on_event("shutdown")
async def shutdown():
    """Clean up on shutdown."""
    if event_bus:
        await event_bus.stop()
    
    if plugin_manager:
        await plugin_manager.stop()
    
    logger.info("Plugin Manager API stopped")


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.get("/plugins", response_model=PluginListResponse)
async def list_plugins():
    """List all loaded plugins."""
    if not plugin_manager:
        raise HTTPException(status_code=503, detail="Plugin manager not initialized")
    
    return PluginListResponse(plugins=plugin_manager.get_plugin_status())


@app.post("/plugins/reload")
async def reload_plugins():
    """Hot reload all plugins."""
    if not plugin_manager:
        raise HTTPException(status_code=503, detail="Plugin manager not initialized")
    
    await plugin_manager.reload_plugins()
    
    return {
        "status": "reloaded",
        "plugins": list(plugin_manager.plugins.keys())
    }


@app.get("/plugins/{name}/logs", response_class=PlainTextResponse)
async def get_plugin_logs(name: str, lines: int = 100):
    """Get recent logs for a plugin."""
    if not plugin_manager:
        raise HTTPException(status_code=503, detail="Plugin manager not initialized")
    
    if name not in plugin_manager.plugins:
        raise HTTPException(status_code=404, detail=f"Plugin {name} not found")
    
    # Read log file
    log_file = plugin_manager.config.logs_dir / f"{name}.log"
    
    if not log_file.exists():
        return "No logs available"
    
    # Read last N lines
    with open(log_file, "r") as f:
        all_lines = f.readlines()
        last_lines = all_lines[-lines:]
        return "".join(last_lines)


@app.post("/plugins/trigger", response_model=TriggerResponse)
async def trigger_plugin(request: TriggerRequest):
    """Manually trigger a plugin for testing."""
    if not plugin_manager:
        raise HTTPException(status_code=503, detail="Plugin manager not initialized")
    
    try:
        result = await plugin_manager.trigger_plugin_manually(
            request.plugin_name,
            request.event_data
        )
        
        return TriggerResponse(
            success=result.success,
            stdout=result.stdout,
            stderr=result.stderr,
            error=result.error,
            duration_ms=result.duration_ms
        )
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to trigger plugin: {e}")
        raise HTTPException(status_code=500, detail="Internal error")


@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    # TODO: Implement Prometheus metrics
    return PlainTextResponse(
        "# HELP titan_plugin_invocations_total Total plugin invocations\n"
        "# TYPE titan_plugin_invocations_total counter\n"
    )
