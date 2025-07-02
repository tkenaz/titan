"""Plugin Manager configuration."""

from typing import Optional, List
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class SandboxConfig(BaseSettings):
    """Sandbox runtime configuration."""
    runtime: str = "docker"  # docker | podman
    default_cpu: str = "50m"
    default_memory: str = "128Mi"
    timeout_sec: int = 60
    network_mode: str = "none"
    
    # Security settings
    read_only: bool = True
    no_new_privileges: bool = True
    drop_capabilities: List[str] = Field(default_factory=lambda: ["ALL"])
    
    # Volumes
    tmp_size: str = "64Mi"
    work_dir: str = "/workspace"


class PluginManagerConfig(BaseSettings):
    """Main Plugin Manager configuration."""
    model_config = SettingsConfigDict(
        env_prefix="PLUGIN_",
        env_nested_delimiter="__",
        env_file=".env",
        extra="ignore"
    )
    
    # Paths
    plugins_dir: Path = Path("plugins")
    logs_dir: Path = Path("logs/plugins")
    
    # Event Bus
    event_bus_url: str = "redis://titan-redis:6379/0"
    consumer_group: str = "plugins"
    
    # Sandbox
    sandbox: SandboxConfig = Field(default_factory=SandboxConfig)
    
    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8003
    
    # Performance
    max_concurrent_plugins: int = 5
    task_queue_size: int = 100
    
    # Observability
    metrics_port: int = 8004
    log_max_lines: int = 1000
    
    @classmethod
    def from_yaml(cls, path: str) -> "PluginManagerConfig":
        """Load configuration from YAML file."""
        import yaml
        
        with open(path, "r") as f:
            data = yaml.safe_load(f)
        
        if "sandbox" in data:
            data["sandbox"] = SandboxConfig(**data["sandbox"])
        
        return cls(**data)
