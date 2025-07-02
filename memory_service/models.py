"""Data models for Memory Service."""

from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any
import ulid

from pydantic import BaseModel, Field, field_validator
import numpy as np


class StaticPriority(str, Enum):
    """Static priority levels for memories."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ImportanceWeights(BaseModel):
    """Weights for importance calculation."""
    personal: float = 0.9
    technical: float = 0.8
    temporal: float = 0.9
    emotional: float = 0.7
    correction: float = 1.0


class MemoryFeatures(BaseModel):
    """Extracted features for importance calculation."""
    is_personal: bool = False
    is_technical: bool = False
    has_temporal: bool = False
    emotional_weight: float = 0.0
    is_correction: bool = False
    entities: List[str] = Field(default_factory=list)


class MemoryEntry(BaseModel):
    """Core memory entry model."""
    id: str = Field(default_factory=lambda: str(ulid.new()))
    summary: str
    embedding: Optional[List[float]] = None
    embedding_model: str = "text-embedding-3-small"
    static_priority: StaticPriority = StaticPriority.MEDIUM
    usage_count: int = 1
    last_accessed: datetime = Field(default_factory=datetime.utcnow)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    tags: List[str] = Field(default_factory=list)
    emotional_weight: float = 0.0
    source: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    @field_validator("summary")
    def validate_summary(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Summary cannot be empty")
        if len(v) > 1000:  # Reasonable limit
            raise ValueError("Summary too long (max 1000 chars)")
        return v.strip()
    
    @field_validator("embedding")
    def validate_embedding(cls, v: Optional[List[float]]) -> Optional[List[float]]:
        if v is not None:
            if not isinstance(v, list) or not all(isinstance(x, (int, float)) for x in v):
                raise ValueError("Embedding must be a list of numbers")
            # OpenAI embeddings are typically 1536 dimensions
            if len(v) not in [384, 768, 1536, 3072]:  # Common embedding sizes
                raise ValueError(f"Unexpected embedding dimension: {len(v)}")
        return v
    
    def to_vector_format(self) -> np.ndarray:
        """Convert embedding to numpy array for pgvector."""
        if self.embedding is None:
            raise ValueError("No embedding available")
        return np.array(self.embedding, dtype=np.float32)
    
    def calculate_decay_score(self, days_old: float) -> float:
        """Calculate decay score for garbage collection."""
        decay = self.usage_count / (1 + days_old)
        return decay + self.emotional_weight


class MemorySearchResult(BaseModel):
    """Search result with similarity score."""
    memory: MemoryEntry
    similarity: float
    highlights: Optional[List[str]] = None


class EvaluationRequest(BaseModel):
    """Request to evaluate a message for memory storage."""
    message: str
    context: Optional[Dict[str, Any]] = None
    source: Optional[str] = None


class EvaluationResponse(BaseModel):
    """Response from memory evaluation."""
    saved: bool
    id: Optional[str] = None
    importance_score: Optional[float] = None
    reason: Optional[str] = None


class SearchRequest(BaseModel):
    """Memory search request."""
    query: str
    k: int = Field(default=10, ge=1, le=100)
    tags: Optional[List[str]] = None
    min_similarity: float = Field(default=0.5, ge=0.0, le=1.0)


class RememberRequest(BaseModel):
    """Explicit remember request."""
    text: str
    tags: Optional[List[str]] = None
    priority: StaticPriority = StaticPriority.MEDIUM
    metadata: Optional[Dict[str, Any]] = None


class ForgetRequest(BaseModel):
    """Request to forget a memory."""
    id: str
    reason: Optional[str] = None


class RecentMessage(BaseModel):
    """Recent message in short-term cache."""
    id: str
    text: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    entities: List[str] = Field(default_factory=list)
    source: Optional[str] = None
