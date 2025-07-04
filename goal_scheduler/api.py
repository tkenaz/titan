"""Goal Scheduler API."""

import os
from contextlib import asynccontextmanager
from typing import Optional, List
from datetime import datetime

from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware

from goal_scheduler.config import SchedulerConfig
from goal_scheduler.models import (
    GoalRunRequest, GoalListResponse, 
    GoalDetailResponse, GoalState
)
from goal_scheduler.scheduler import GoalScheduler

# Global scheduler instance
scheduler: Optional[GoalScheduler] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan."""
    global scheduler
    
    # Startup
    config = SchedulerConfig.from_env()
    scheduler = GoalScheduler(config)
    await scheduler.start()
    
    yield
    
    # Shutdown
    if scheduler:
        await scheduler.stop()


# Initialize FastAPI app
app = FastAPI(
    title="Titan Goal Scheduler API",
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
security = HTTPBearer(auto_error=False)


async def verify_token(request: Request, credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> Optional[str]:
    """Verify Bearer token."""
    # Skip auth for OPTIONS requests (CORS preflight)
    if request.method == "OPTIONS":
        return None
    
    if not credentials:
        raise HTTPException(
            status_code=401,
            detail="Missing authorization header"
        )
    
    token = credentials.credentials
    expected_token = os.getenv("ADMIN_TOKEN", "titan-secret-token-change-me-in-production")
    
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
    return {"status": "healthy", "service": "goal-scheduler"}


# List all goals
@app.get("/goals", dependencies=[Depends(verify_token)])
async def list_goals() -> GoalListResponse:
    """List all goals with their current status."""
    if not scheduler:
        raise HTTPException(status_code=503, detail="Scheduler not initialized")
    
    goals = []
    
    # Get all goal configs
    for goal_id, goal_config in scheduler.loader.goals.items():
        # Get latest instance
        instances = await scheduler.storage.get_instances_by_goal(goal_id)
        
        latest_instance = instances[0] if instances else None
        
        goal_info = {
            "id": goal_id,
            "name": goal_config.name,
            "enabled": goal_config.enabled,
            "schedule": goal_config.schedule,
            "trigger_count": len(goal_config.triggers),
            "state": latest_instance.state.value if latest_instance else "NO_RUNS",
            "last_run": latest_instance.started_at.isoformat() if latest_instance and latest_instance.started_at else None,
            "next_run": datetime.fromtimestamp(latest_instance.next_run_ts).isoformat() if latest_instance and latest_instance.next_run_ts else None
        }
        
        goals.append(goal_info)
    
    return GoalListResponse(goals=goals, total=len(goals))


# Get goal details
@app.get("/goals/{goal_id}", dependencies=[Depends(verify_token)])
async def get_goal(goal_id: str) -> GoalDetailResponse:
    """Get detailed information about a goal."""
    if not scheduler:
        raise HTTPException(status_code=503, detail="Scheduler not initialized")
    
    # Get goal config
    goal_config = scheduler.loader.get_goal(goal_id)
    if not goal_config:
        raise HTTPException(status_code=404, detail=f"Goal {goal_id} not found")
    
    # Get instances
    instances = await scheduler.storage.get_instances_by_goal(goal_id)
    
    # Calculate next run
    next_run = None
    if goal_config.schedule:
        next_run_ts = scheduler._calculate_next_run(goal_config.schedule)
        if next_run_ts:
            next_run = datetime.fromtimestamp(next_run_ts)
    
    return GoalDetailResponse(
        config=goal_config,
        instances=instances[:10],  # Last 10 instances
        next_run=next_run
    )


# Run goal immediately
@app.post("/goals/run", dependencies=[Depends(verify_token)])
async def run_goal(request: GoalRunRequest) -> dict:
    """Run a goal immediately."""
    if not scheduler:
        raise HTTPException(status_code=503, detail="Scheduler not initialized")
    
    try:
        instance_id = await scheduler.run_goal_now(request.goal_id, request.params)
        return {
            "instance_id": instance_id,
            "message": f"Goal {request.goal_id} queued for execution"
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# Pause goal instance
@app.post("/goals/{instance_id}/pause", dependencies=[Depends(verify_token)])
async def pause_goal(instance_id: str) -> dict:
    """Pause a running goal instance."""
    if not scheduler:
        raise HTTPException(status_code=503, detail="Scheduler not initialized")
    
    await scheduler.pause_goal(instance_id)
    return {"message": f"Goal instance {instance_id} paused"}


# Resume goal instance
@app.post("/goals/{instance_id}/resume", dependencies=[Depends(verify_token)])
async def resume_goal(instance_id: str) -> dict:
    """Resume a paused goal instance."""
    if not scheduler:
        raise HTTPException(status_code=503, detail="Scheduler not initialized")
    
    await scheduler.resume_goal(instance_id)
    return {"message": f"Goal instance {instance_id} resumed"}


# Reload goal configurations
@app.post("/goals/reload", dependencies=[Depends(verify_token)])
async def reload_goals() -> dict:
    """Reload goal configurations from YAML files."""
    if not scheduler:
        raise HTTPException(status_code=503, detail="Scheduler not initialized")
    
    goals = scheduler.loader.reload()
    return {
        "message": "Goals reloaded",
        "loaded": len(goals),
        "goals": list(goals.keys())
    }


if __name__ == "__main__":
    import uvicorn
    
    config = SchedulerConfig.from_env()
    uvicorn.run(app, host=config.api_host, port=config.api_port)
