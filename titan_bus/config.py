"""Configuration for Titan Event Bus."""

from typing import Dict, List, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
import yaml


class StreamConfig(BaseSettings):
    """Configuration for a single stream."""
    name: str
    maxlen: int = 1_000_000
    rate_limit: int = 100  # messages per second
    retry_limit: int = 5
    
    @field_validator("name")
    def validate_versioned_name(cls, v: str) -> str:
        if not any(v.endswith(f".v{i}") for i in range(1, 10)):
            raise ValueError(f"Stream name must be versioned (e.g., {v}.v1)")
        return v


class RedisConfig(BaseSettings):
    """Redis configuration."""
    url: str = "redis://localhost:6379/0"
    password: Optional[str] = None
    ssl: bool = False
    pool_size: int = 10
    decode_responses: bool = False


class EventBusConfig(BaseSettings):
    """Main Event Bus configuration."""
    model_config = SettingsConfigDict(
        env_prefix="TITAN_",
        env_nested_delimiter="__",
        env_file=".env",
        extra="ignore"
    )
    
    redis: RedisConfig = Field(default_factory=RedisConfig)
    streams: List[StreamConfig] = Field(default_factory=list)
    priority_weights: Dict[str, int] = Field(
        default_factory=lambda: {"high": 3, "medium": 2, "low": 1}
    )
    
    # Global settings
    batch_size: int = 100
    block_timeout: int = 2000  # milliseconds
    consumer_group: str = "titan-core"
    dead_letter_stream: str = "errors.dlq"
    max_global_rate: int = 1000  # messages per second
    
    # Observability
    metrics_port: int = 8000
    trace_sample_rate: float = 0.1
    
    @classmethod
    def from_yaml(cls, path: str) -> "EventBusConfig":
        """Load configuration from YAML file."""
        with open(path, "r") as f:
            data = yaml.safe_load(f)
        
        # Convert stream configs
        if "streams" in data:
            data["streams"] = [StreamConfig(**stream) for stream in data["streams"]]
        
        # Convert redis config
        if "redis" in data:
            data["redis"] = RedisConfig(**data["redis"])
            
        return cls(**data)
    
    def get_stream_config(self, topic: str) -> Optional[StreamConfig]:
        """Get configuration for a specific topic."""
        for stream in self.streams:
            if stream.name == topic:
                return stream
        return None
