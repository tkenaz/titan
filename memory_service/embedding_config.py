"""Embedding models configuration and optimal thresholds."""

from typing import Dict, NamedTuple


class EmbeddingConfig(NamedTuple):
    """Configuration for embedding model."""
    dimension: int
    default_search_threshold: float
    duplicate_threshold: float
    description: str


# Optimal thresholds for different embedding models
EMBEDDING_CONFIGS: Dict[str, EmbeddingConfig] = {
    "text-embedding-3-small": EmbeddingConfig(
        dimension=1536,
        default_search_threshold=0.4,  # Lower threshold for partial matches
        duplicate_threshold=0.9,       # High threshold for duplicates
        description="OpenAI's small model, fast and cheap"
    ),
    "text-embedding-3-large": EmbeddingConfig(
        dimension=3072,
        default_search_threshold=0.45,
        duplicate_threshold=0.92,
        description="OpenAI's large model, more accurate"
    ),
    "text-embedding-ada-002": EmbeddingConfig(
        dimension=1536,
        default_search_threshold=0.35,  # Older model needs lower threshold
        duplicate_threshold=0.85,
        description="OpenAI's legacy model"
    ),
    "e5-large": EmbeddingConfig(
        dimension=1024,
        default_search_threshold=0.5,
        duplicate_threshold=0.9,
        description="Local multilingual model for ML evaluator"
    ),
    "sentence-transformers/all-MiniLM-L6-v2": EmbeddingConfig(
        dimension=384,
        default_search_threshold=0.45,
        duplicate_threshold=0.85,
        description="Lightweight local model"
    )
}


def get_optimal_thresholds(model_name: str) -> tuple[float, float]:
    """Get optimal search and duplicate thresholds for a model."""
    config = EMBEDDING_CONFIGS.get(model_name)
    if not config:
        # Default conservative thresholds
        return 0.5, 0.9
    return config.default_search_threshold, config.duplicate_threshold


# Usage tips for different search scenarios
SEARCH_SCENARIOS = {
    "exact_phrase": {
        "threshold_modifier": 0.2,   # Add to base threshold
        "description": "Looking for exact phrases or names"
    },
    "semantic_similar": {
        "threshold_modifier": 0.0,   # Use base threshold
        "description": "General semantic similarity"
    },
    "broad_topic": {
        "threshold_modifier": -0.1,  # Subtract from base threshold
        "description": "Broad topic search, allow more results"
    },
    "cross_language": {
        "threshold_modifier": -0.15, # Lower threshold for cross-language
        "description": "Searching across languages (RU/EN)"
    }
}
