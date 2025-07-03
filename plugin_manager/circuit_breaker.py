"""Circuit Breaker for Plugin Manager - prevents cascading failures."""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional
from enum import Enum
from dataclasses import dataclass, field

import redis.asyncio as redis
from prometheus_client import Counter, Gauge

logger = logging.getLogger(__name__)


class PluginState(str, Enum):
    """Plugin operational states."""
    ACTIVE = "active"
    DISABLED = "disabled"
    PAUSED = "paused"


@dataclass
class PluginHealth:
    """Track plugin health metrics."""
    name: str
    state: PluginState = PluginState.ACTIVE
    consecutive_failures: int = 0
    total_failures: int = 0
    total_executions: int = 0
    last_failure: Optional[datetime] = None
    last_success: Optional[datetime] = None
    disabled_until: Optional[datetime] = None
    failure_reasons: list = field(default_factory=list)


class CircuitBreaker:
    """Circuit breaker for plugin execution."""
    
    def __init__(
        self,
        redis_client: redis.Redis,
        failure_threshold: int = 5,
        reset_timeout: int = 300,  # 5 minutes
        max_failure_history: int = 10
    ):
        self.redis = redis_client
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self.max_failure_history = max_failure_history
        self.health_data: Dict[str, PluginHealth] = {}
        
        # Metrics
        self.plugin_errors = Counter(
            'titan_plugin_errors_total',
            'Total plugin errors',
            ['plugin', 'error_type']
        )
        self.plugin_disabled = Counter(
            'titan_plugin_disabled_total',
            'Times plugin was disabled',
            ['plugin']
        )
        self.plugin_state = Gauge(
            'titan_plugin_state',
            'Current plugin state (0=disabled, 1=active, 2=paused)',
            ['plugin']
        )
    
    async def initialize(self, plugin_names: list[str]):
        """Initialize health tracking for plugins."""
        for name in plugin_names:
            # Try to load state from Redis
            saved_state = await self._load_state(name)
            if saved_state:
                self.health_data[name] = saved_state
            else:
                self.health_data[name] = PluginHealth(name=name)
            
            # Update metrics
            self._update_state_metric(name)
    
    async def record_success(self, plugin_name: str):
        """Record successful plugin execution."""
        health = self.health_data.get(plugin_name)
        if not health:
            return
        
        health.consecutive_failures = 0
        health.total_executions += 1
        health.last_success = datetime.utcnow()
        
        # Reset state if it was paused and timeout expired
        if health.state == PluginState.PAUSED:
            if health.disabled_until and datetime.utcnow() > health.disabled_until:
                health.state = PluginState.ACTIVE
                health.disabled_until = None
                logger.info(f"Plugin {plugin_name} re-enabled after timeout")
        
        await self._save_state(plugin_name, health)
        self._update_state_metric(plugin_name)
    
    async def record_failure(
        self,
        plugin_name: str,
        error: Exception,
        event_data: Optional[dict] = None
    ) -> bool:
        """
        Record plugin failure and check if it should be disabled.
        Returns True if plugin should be disabled.
        """
        health = self.health_data.get(plugin_name)
        if not health:
            return False
        
        # Update counters
        health.consecutive_failures += 1
        health.total_failures += 1
        health.total_executions += 1
        health.last_failure = datetime.utcnow()
        
        # Track error reason
        error_info = {
            "timestamp": health.last_failure.isoformat(),
            "error": str(error),
            "type": type(error).__name__,
            "event": event_data.get("event_type") if event_data else None
        }
        health.failure_reasons.append(error_info)
        
        # Keep only last N failures
        if len(health.failure_reasons) > self.max_failure_history:
            health.failure_reasons = health.failure_reasons[-self.max_failure_history:]
        
        # Update metrics
        self.plugin_errors.labels(
            plugin=plugin_name,
            error_type=type(error).__name__
        ).inc()
        
        # Check if we should disable the plugin
        should_disable = False
        if health.consecutive_failures >= self.failure_threshold:
            health.state = PluginState.DISABLED
            health.disabled_until = datetime.utcnow() + timedelta(seconds=self.reset_timeout)
            should_disable = True
            
            logger.error(
                f"Plugin {plugin_name} DISABLED after {health.consecutive_failures} failures. "
                f"Will retry at {health.disabled_until}"
            )
            
            self.plugin_disabled.labels(plugin=plugin_name).inc()
            
            # Publish alert event
            await self._publish_alert(plugin_name, health)
        
        await self._save_state(plugin_name, health)
        self._update_state_metric(plugin_name)
        
        return should_disable
    
    async def is_plugin_healthy(self, plugin_name: str) -> bool:
        """Check if plugin is healthy and can execute."""
        health = self.health_data.get(plugin_name)
        if not health:
            return True
        
        # Check if disabled
        if health.state == PluginState.DISABLED:
            return False
        
        # Check if paused and timeout not expired
        if health.state == PluginState.PAUSED:
            if health.disabled_until and datetime.utcnow() < health.disabled_until:
                return False
        
        return True
    
    async def get_plugin_health(self, plugin_name: str) -> Optional[PluginHealth]:
        """Get current health status of a plugin."""
        return self.health_data.get(plugin_name)
    
    async def reset_plugin(self, plugin_name: str):
        """Manually reset plugin to healthy state."""
        health = self.health_data.get(plugin_name)
        if not health:
            return
        
        health.state = PluginState.ACTIVE
        health.consecutive_failures = 0
        health.disabled_until = None
        
        await self._save_state(plugin_name, health)
        self._update_state_metric(plugin_name)
        
        logger.info(f"Plugin {plugin_name} manually reset to ACTIVE")
    
    async def pause_plugin(self, plugin_name: str, minutes: int = 60):
        """Manually pause plugin for specified minutes."""
        health = self.health_data.get(plugin_name)
        if not health:
            return
        
        health.state = PluginState.PAUSED
        health.disabled_until = datetime.utcnow() + timedelta(minutes=minutes)
        
        await self._save_state(plugin_name, health)
        self._update_state_metric(plugin_name)
        
        logger.info(f"Plugin {plugin_name} paused until {health.disabled_until}")
    
    async def _save_state(self, plugin_name: str, health: PluginHealth):
        """Save plugin state to Redis."""
        key = f"plugin:health:{plugin_name}"
        data = {
            "state": health.state.value,
            "consecutive_failures": health.consecutive_failures,
            "total_failures": health.total_failures,
            "total_executions": health.total_executions,
            "last_failure": health.last_failure.isoformat() if health.last_failure else None,
            "last_success": health.last_success.isoformat() if health.last_success else None,
            "disabled_until": health.disabled_until.isoformat() if health.disabled_until else None,
            "failure_reasons": health.failure_reasons
        }
        
        await self.redis.hset(key, mapping={
            k: str(v) if v is not None else ""
            for k, v in data.items()
        })
        
        # Set expiry for 7 days
        await self.redis.expire(key, 7 * 24 * 3600)
    
    async def _load_state(self, plugin_name: str) -> Optional[PluginHealth]:
        """Load plugin state from Redis."""
        key = f"plugin:health:{plugin_name}"
        data = await self.redis.hgetall(key)
        
        if not data:
            return None
        
        # Parse saved data
        health = PluginHealth(name=plugin_name)
        
        if data.get(b'state'):
            health.state = PluginState(data[b'state'].decode())
        
        if data.get(b'consecutive_failures'):
            health.consecutive_failures = int(data[b'consecutive_failures'])
        
        if data.get(b'total_failures'):
            health.total_failures = int(data[b'total_failures'])
            
        if data.get(b'total_executions'):
            health.total_executions = int(data[b'total_executions'])
        
        # Parse dates
        for field in ['last_failure', 'last_success', 'disabled_until']:
            value = data.get(field.encode())
            if value and value != b'':
                setattr(health, field, datetime.fromisoformat(value.decode()))
        
        return health
    
    async def _publish_alert(self, plugin_name: str, health: PluginHealth):
        """Publish alert event when plugin is disabled."""
        from titan_bus import EventBusClient
        
        # This assumes event bus client is available
        # In real implementation, pass it as dependency
        alert_payload = {
            "plugin": plugin_name,
            "state": health.state.value,
            "consecutive_failures": health.consecutive_failures,
            "total_failures": health.total_failures,
            "last_errors": health.failure_reasons[-3:],  # Last 3 errors
            "disabled_until": health.disabled_until.isoformat() if health.disabled_until else None,
            "message": f"Plugin {plugin_name} disabled after {health.consecutive_failures} consecutive failures"
        }
        
        # In production, publish to event bus
        logger.error(f"ALERT: {alert_payload['message']}")
    
    def _update_state_metric(self, plugin_name: str):
        """Update Prometheus metric for plugin state."""
        health = self.health_data.get(plugin_name)
        if not health:
            return
        
        state_value = {
            PluginState.DISABLED: 0,
            PluginState.ACTIVE: 1,
            PluginState.PAUSED: 2
        }
        
        self.plugin_state.labels(plugin=plugin_name).set(
            state_value.get(health.state, 1)
        )
    
    async def get_all_health_status(self) -> Dict[str, dict]:
        """Get health status for all plugins."""
        result = {}
        for name, health in self.health_data.items():
            result[name] = {
                "name": name,
                "state": health.state.value,
                "healthy": await self.is_plugin_healthy(name),
                "consecutive_failures": health.consecutive_failures,
                "total_failures": health.total_failures,
                "total_executions": health.total_executions,
                "success_rate": (
                    (health.total_executions - health.total_failures) / health.total_executions * 100
                    if health.total_executions > 0 else 100
                ),
                "last_failure": health.last_failure.isoformat() if health.last_failure else None,
                "last_success": health.last_success.isoformat() if health.last_success else None,
                "disabled_until": health.disabled_until.isoformat() if health.disabled_until else None
            }
        
        return result
