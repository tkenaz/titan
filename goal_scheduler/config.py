"""Goal Scheduler configuration."""

import os
from typing import Optional, List
from pydantic import BaseModel, Field


class SchedulerConfig(BaseModel):
    """Configuration for Goal Scheduler."""
    
    # Redis connection
    redis_url: str = Field(
        default="redis://localhost:6379/2",
        description="Redis URL for goal state storage (using DB 2)"
    )
    
    # Goal definitions
    goals_dir: str = Field(
        default="./goals",
        description="Directory containing goal YAML files"
    )
    
    # Scheduler settings
    loop_interval_sec: int = Field(
        default=10,
        description="How often to check for goals to run"
    )
    
    default_timeout_sec: int = Field(
        default=300,
        description="Default timeout for goal execution"
    )
    
    max_concurrent_goals: int = Field(
        default=5,
        description="Maximum number of goals running concurrently"
    )
    
    # Event Bus integration
    event_bus_url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis URL for Event Bus"
    )
    
    consumer_group: str = Field(
        default="goal-scheduler",
        description="Consumer group name for Event Bus"
    )
    
    # API settings
    api_host: str = Field(default="0.0.0.0")
    api_port: int = Field(default=8005)
    
    # Observability
    metrics_port: int = Field(default=8006)
    log_level: str = Field(default="INFO")
    
    @classmethod
    def from_env(cls) -> 'SchedulerConfig':
        """Create config from environment variables."""
        return cls(
            redis_url=os.getenv("SCHEDULER_REDIS_URL", cls.model_fields['redis_url'].default),
            goals_dir=os.getenv("GOALS_DIR", cls.model_fields['goals_dir'].default),
            loop_interval_sec=int(os.getenv("SCHEDULER_LOOP_INTERVAL", "10")),
            event_bus_url=os.getenv("EVENT_BUS_URL", cls.model_fields['event_bus_url'].default),
            api_host=os.getenv("SCHEDULER_API_HOST", cls.model_fields['api_host'].default),
            api_port=int(os.getenv("SCHEDULER_API_PORT", "8005"))
        )
