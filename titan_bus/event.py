"""Event models for Titan Event Bus."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field, field_validator
import ulid


class EventPriority(str, Enum):
    """Event priority levels."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class EventMeta(BaseModel):
    """Event metadata."""
    priority: EventPriority = EventPriority.MEDIUM
    retries: int = 0
    trace_id: Optional[str] = None
    source: Optional[str] = None
    
    @field_validator("retries")
    def validate_retries(cls, v: int) -> int:
        if v < 0:
            raise ValueError("Retries cannot be negative")
        return v


class Event(BaseModel):
    """Core event model."""
    event_id: str = Field(default_factory=lambda: str(ulid.new()))
    schema_version: int = 1
    topic: str
    event_type: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    payload: Dict[str, Any]
    meta: EventMeta = Field(default_factory=EventMeta)
    
    @field_validator("topic")
    def validate_topic(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Topic cannot be empty")
        # Ensure versioned topics
        if not any(v.endswith(f".v{i}") for i in range(1, 10)):
            raise ValueError(f"Topic must be versioned (e.g., {v}.v1)")
        return v
    
    @field_validator("payload")
    def validate_payload_size(cls, v: Dict[str, Any]) -> Dict[str, Any]:
        # Simple size check (32KB limit)
        import json
        size = len(json.dumps(v).encode('utf-8'))
        if size > 32 * 1024:  # 32KB
            raise ValueError(f"Payload size {size} exceeds 32KB limit")
        return v
    
    def to_redis(self) -> Dict[str, str]:
        """Convert to Redis-compatible format."""
        return {
            "data": self.model_dump_json()
        }
    
    @classmethod
    def from_redis(cls, data: Dict[bytes, bytes]) -> "Event":
        """Create Event from Redis data."""
        import json
        json_data = data[b"data"].decode("utf-8")
        return cls.model_validate(json.loads(json_data))
    
    def increment_retry(self) -> "Event":
        """Increment retry count and return new event."""
        return self.model_copy(update={"meta": self.meta.model_copy(update={"retries": self.meta.retries + 1})})
