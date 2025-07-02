"""Plugin models and configuration schemas."""

from typing import Dict, List, Optional, Any
from pathlib import Path
from enum import Enum
import re

from pydantic import BaseModel, Field, field_validator


class ResourceLimits(BaseModel):
    """Resource limits for plugin execution."""
    cpu: str = "50m"  # Kubernetes-style CPU units
    memory: str = "128Mi"  # Kubernetes-style memory units
    
    @field_validator("cpu")
    def validate_cpu(cls, v: str) -> str:
        # Validate CPU format: 100m, 0.5, 1, etc.
        if not re.match(r"^\d+(\.\d+)?$|^\d+m$", v):
            raise ValueError(f"Invalid CPU format: {v}")
        return v
    
    @field_validator("memory")
    def validate_memory(cls, v: str) -> str:
        # Validate memory format: 128Mi, 1Gi, etc.
        if not re.match(r"^\d+(Ki|Mi|Gi)$", v):
            raise ValueError(f"Invalid memory format: {v}")
        return v


class FilePermissions(BaseModel):
    """File system permissions for plugin."""
    allow: List[str] = Field(default_factory=list)
    deny: List[str] = Field(default_factory=list)
    
    def is_allowed(self, path: Path) -> bool:
        """Check if path is allowed for access."""
        path_str = str(path.absolute())
        
        # Check deny list first (takes precedence)
        for pattern in self.deny:
            if self._match_pattern(path_str, pattern):
                return False
        
        # Then check allow list
        for pattern in self.allow:
            if self._match_pattern(path_str, pattern):
                return True
        
        # Default deny if not explicitly allowed
        return False
    
    def _match_pattern(self, path: str, pattern: str) -> bool:
        """Match path against glob pattern."""
        import fnmatch
        return fnmatch.fnmatch(path, pattern)


class PluginPermissions(BaseModel):
    """All permissions for a plugin."""
    fs: Optional[FilePermissions] = None
    network: bool = False  # Network access (default: no)
    commands: List[str] = Field(default_factory=list)  # Allowed shell commands


class EventTrigger(BaseModel):
    """Event trigger configuration."""
    topic: str
    event_type: Optional[str] = None
    filter: Optional[Dict[str, Any]] = None  # Additional filters on payload


class PluginStatus(str, Enum):
    """Plugin status."""
    LOADED = "loaded"
    RUNNING = "running"
    ERROR = "error"
    DISABLED = "disabled"


class PluginConfig(BaseModel):
    """Plugin configuration from plugin.yaml."""
    name: str
    version: str
    description: Optional[str] = None
    author: Optional[str] = None
    
    # Triggers
    triggers: List[EventTrigger]
    
    # Runtime
    entrypoint: str
    image: str = "python:3.12-slim"  # Docker image
    requirements: List[str] = Field(default_factory=list)  # Python packages
    
    # Resources and permissions
    resources: ResourceLimits = Field(default_factory=ResourceLimits)
    permissions: PluginPermissions = Field(default_factory=PluginPermissions)
    
    # Timeouts
    timeout_sec: int = 60
    
    @field_validator("name")
    def validate_name(cls, v: str) -> str:
        if not re.match(r"^[a-z][a-z0-9_-]*$", v):
            raise ValueError(f"Invalid plugin name: {v}")
        return v
    
    @field_validator("version")
    def validate_version(cls, v: str) -> str:
        # Basic semver validation
        if not re.match(r"^\d+\.\d+\.\d+(-\w+)?$", v):
            raise ValueError(f"Invalid version format: {v}")
        return v
    
    @classmethod
    def from_yaml(cls, path: Path) -> "PluginConfig":
        """Load plugin config from YAML file."""
        import yaml
        
        with open(path, "r") as f:
            data = yaml.safe_load(f)
        
        # Convert nested objects
        if "triggers" in data:
            data["triggers"] = [EventTrigger(**t) for t in data["triggers"]]
        
        if "resources" in data:
            data["resources"] = ResourceLimits(**data["resources"])
        
        if "permissions" in data:
            perms = data["permissions"]
            if "fs" in perms:
                perms["fs"] = FilePermissions(**perms["fs"])
            data["permissions"] = PluginPermissions(**perms)
        
        return cls(**data)


class PluginInstance(BaseModel):
    """Runtime instance of a plugin."""
    config: PluginConfig
    path: Path
    status: PluginStatus = PluginStatus.LOADED
    error: Optional[str] = None
    invocation_count: int = 0
    error_count: int = 0
    last_run: Optional[str] = None
    
    class Config:
        arbitrary_types_allowed = True


class PluginTask(BaseModel):
    """Task to execute a plugin."""
    plugin_name: str
    event: Dict[str, Any]
    event_id: str
    timestamp: str
    
    
class PluginResult(BaseModel):
    """Result of plugin execution."""
    plugin_name: str
    event_id: str
    success: bool
    stdout: Optional[str] = None
    stderr: Optional[str] = None
    exit_code: int = 0
    duration_ms: float = 0
    error: Optional[str] = None
