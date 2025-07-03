"""Goal Scheduler data models."""

from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any, Union
from pydantic import BaseModel, Field, validator
import yaml


class GoalState(str, Enum):
    """Goal execution states."""
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    FAILED = "FAILED"
    SUCCEEDED = "SUCCEEDED"
    PAUSED = "PAUSED"


class StepType(str, Enum):
    """Types of goal steps."""
    PLUGIN = "plugin"
    BUS_EVENT = "bus_event"
    INTERNAL = "internal"


class RetryConfig(BaseModel):
    """Retry configuration for goals."""
    attempts: int = 3
    backoff_sec: int = 30


class EventTrigger(BaseModel):
    """Event trigger configuration."""
    topic: str
    event_type: Optional[str] = None
    filter: Optional[Dict[str, Any]] = None


class GoalStep(BaseModel):
    """Single step in a goal execution."""
    id: str
    type: StepType
    plugin: Optional[str] = None  # For PLUGIN type
    topic: Optional[str] = None   # For BUS_EVENT type
    event_type: Optional[str] = None  # For BUS_EVENT type
    params: Optional[Dict[str, Any]] = None
    payload_template: Optional[str] = None
    timeout_sec: int = 60
    
    @validator('plugin')
    def plugin_required_for_plugin_type(cls, v, values):
        if values.get('type') == StepType.PLUGIN and not v:
            raise ValueError('plugin name required for PLUGIN step type')
        return v
    
    @validator('topic')
    def topic_required_for_bus_event(cls, v, values):
        if values.get('type') == StepType.BUS_EVENT and not v:
            raise ValueError('topic required for BUS_EVENT step type')
        return v


class GoalConfig(BaseModel):
    """Goal configuration from YAML."""
    id: str
    name: str
    schedule: Optional[str] = None  # Cron expression or @every format
    triggers: List[EventTrigger] = Field(default_factory=list)
    steps: List[GoalStep]
    retry: RetryConfig = Field(default_factory=RetryConfig)
    timeout_sec: int = 300
    enabled: bool = True
    
    @validator('schedule')
    def validate_schedule_or_triggers(cls, v, values):
        triggers = values.get('triggers', [])
        if not v and not triggers:
            raise ValueError('Either schedule or triggers must be specified')
        return v
    
    @classmethod
    def from_yaml(cls, yaml_content: str) -> 'GoalConfig':
        """Load goal configuration from YAML."""
        data = yaml.safe_load(yaml_content)
        return cls(**data)
    
    @classmethod
    def from_file(cls, file_path: str) -> 'GoalConfig':
        """Load goal configuration from YAML file."""
        with open(file_path, 'r') as f:
            return cls.from_yaml(f.read())


class GoalInstance(BaseModel):
    """Runtime instance of a goal."""
    id: str  # Unique instance ID (goal_id + timestamp)
    goal_id: str  # Reference to GoalConfig.id
    state: GoalState = GoalState.PENDING
    current_step: int = 0
    next_run_ts: Optional[float] = None
    fail_count: int = 0
    last_error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    trigger_event: Optional[Dict[str, Any]] = None  # Event that triggered this instance
    step_results: Dict[str, Any] = Field(default_factory=dict)  # Results from each step
    
    def to_redis_hash(self) -> Dict[str, str]:
        """Convert to Redis hash format."""
        return {
            'goal_id': self.goal_id,
            'state': self.state.value,
            'current_step': str(self.current_step),
            'next_run_ts': str(self.next_run_ts) if self.next_run_ts else '',
            'fail_count': str(self.fail_count),
            'last_error': self.last_error or '',
            'started_at': self.started_at.isoformat() if self.started_at else '',
            'completed_at': self.completed_at.isoformat() if self.completed_at else '',
            'trigger_event': yaml.dump(self.trigger_event) if self.trigger_event else '',
            'step_results': yaml.dump(self.step_results)
        }
    
    @classmethod
    def from_redis_hash(cls, instance_id: str, data: Dict[str, str]) -> 'GoalInstance':
        """Create from Redis hash data."""
        return cls(
            id=instance_id,
            goal_id=data['goal_id'],
            state=GoalState(data['state']),
            current_step=int(data['current_step']),
            next_run_ts=float(data['next_run_ts']) if data['next_run_ts'] else None,
            fail_count=int(data['fail_count']),
            last_error=data['last_error'] or None,
            started_at=datetime.fromisoformat(data['started_at']) if data['started_at'] else None,
            completed_at=datetime.fromisoformat(data['completed_at']) if data['completed_at'] else None,
            trigger_event=yaml.safe_load(data['trigger_event']) if data['trigger_event'] else None,
            step_results=yaml.safe_load(data['step_results']) if data['step_results'] else {}
        )


class GoalRunRequest(BaseModel):
    """Request to run a goal immediately."""
    goal_id: str
    params: Optional[Dict[str, Any]] = None


class GoalListResponse(BaseModel):
    """Response for goal listing."""
    goals: List[Dict[str, Any]]
    total: int


class GoalDetailResponse(BaseModel):
    """Detailed goal information."""
    config: GoalConfig
    instances: List[GoalInstance]
    next_run: Optional[datetime] = None
