"""Plugin Manager package."""

from plugin_manager.enhanced_manager import EnhancedPluginManager
from plugin_manager.config import PluginManagerConfig
from plugin_manager.models import PluginConfig, PluginInstance, PluginStatus

__version__ = "0.1.0"

__all__ = [
    "EnhancedPluginManager",
    "PluginManagerConfig", 
    "PluginConfig",
    "PluginInstance",
    "PluginStatus"
]
