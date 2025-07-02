"""Memory Service - Long-term and short-term memory for Titan."""

from memory_service.models import (
    MemoryEntry,
    StaticPriority,
    ImportanceWeights,
    MemorySearchResult,
)
from memory_service.evaluator import MemoryEvaluator
from memory_service.storage import VectorStorage, GraphStorage, RecentCache
from memory_service.api import app

__version__ = "0.1.0"

__all__ = [
    # Models
    "MemoryEntry",
    "StaticPriority",
    "ImportanceWeights",
    "MemorySearchResult",
    # Core components
    "MemoryEvaluator",
    "VectorStorage",
    "GraphStorage",
    "RecentCache",
    # API
    "app",
]
