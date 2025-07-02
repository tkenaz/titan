"""Configuration for Memory Service."""

import os
from typing import Optional, Dict
import re
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Load .env file if exists
env_path = Path("/app/.env")
if not env_path.exists():
    env_path = Path(".env")
if env_path.exists():
    from dotenv import load_dotenv
    load_dotenv(env_path)


class VectorDBConfig(BaseSettings):
    """PostgreSQL + pgvector configuration."""
    dsn: str = "postgresql://titan:titan@localhost:5432/titan"
    pool_size: int = 10
    
    @field_validator("dsn")
    def validate_dsn(cls, v: str) -> str:
        if not v.startswith("postgresql://"):
            raise ValueError("DSN must start with postgresql://")
        return v


class GraphDBConfig(BaseSettings):
    """Neo4j configuration."""
    uri: str = "bolt://localhost:7687"
    user: str = "neo4j"
    password: str = "password"
    
    @field_validator("uri")
    def validate_uri(cls, v: str) -> str:
        if not re.match(r"^(bolt|neo4j)://", v):
            raise ValueError("URI must start with bolt:// or neo4j://")
        return v


class RedisConfig(BaseSettings):
    """Redis configuration."""
    url: str = "redis://localhost:6379/0"
    ttl_hours: int = 24
    max_recent: int = 200


class MemoryConfig(BaseSettings):
    """Main Memory Service configuration."""
    model_config = SettingsConfigDict(
        env_prefix="MEMORY_",
        env_nested_delimiter="__",
        env_file=".env",
        extra="ignore"
    )
    
    # Storage backends
    vector_db: VectorDBConfig = Field(default_factory=VectorDBConfig)
    graph_db: GraphDBConfig = Field(default_factory=GraphDBConfig)
    redis: RedisConfig = Field(default_factory=RedisConfig)
    
    # Memory evaluation
    importance_threshold: float = 0.75
    gc_threshold: float = 0.25
    embedding_model: str = "text-embedding-3-small"
    importance_weights: Dict[str, float] = Field(default_factory=lambda: {
        "personal": 0.9,
        "technical": 0.8,
        "temporal": 0.9,
        "emotional": 0.7,
        "correction": 1.0,
        "plans": 0.9
    })
    
    # API settings
    api_host: str = "0.0.0.0"
    api_port: int = 8001
    
    # Event Bus integration
    event_bus_url: str = "redis://titan-redis:6379/0"
    consumer_group: str = "memory-service"
    
    # OpenAI settings (for embeddings)
    openai_api_key: Optional[str] = None
    
    # Observability
    metrics_port: int = 8002
    trace_sample_rate: float = 0.1
    
    @classmethod
    def from_yaml(cls, path: str) -> "MemoryConfig":
        """Load configuration from YAML file."""
        import yaml
        with open(path, "r") as f:
            data = yaml.safe_load(f)
        
        # Convert nested configs
        if "vector_db" in data:
            data["vector_db"] = VectorDBConfig(**data["vector_db"])
        if "graph_db" in data:
            data["graph_db"] = GraphDBConfig(**data["graph_db"])
        if "redis" in data:
            data["redis"] = RedisConfig(**data["redis"])
        
        # importance_weights will be loaded automatically
            
        return cls(**data)
