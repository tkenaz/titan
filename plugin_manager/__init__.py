"""Plugin Manager package."""

from plugin_manager.manager import PluginManager
from plugin_manager.config import PluginManagerConfig
from plugin_manager.models import PluginConfig, PluginInstance, PluginStatus

__version__ = "0.1.0"

__all__ = [
    "PluginManager",
    "PluginManagerConfig", 
    "PluginConfig",
    "PluginInstance",
    "PluginStatus"
]
