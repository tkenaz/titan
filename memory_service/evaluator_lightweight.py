"""Lightweight ML evaluator without heavy dependencies for testing."""

import logging
from typing import Dict, List, Optional, Tuple
import hashlib

from memory_service.models import (
    MemoryFeatures,
    ImportanceWeights,
    StaticPriority,
)

logger = logging.getLogger(__name__)


class LightweightMLEvaluator:
    """Simplified evaluator that mimics ML behavior without torch dependency."""
    
    # Keywords that boost importance (simulating semantic understanding)
    IMPORTANCE_KEYWORDS = {
        'personal': {'марина', 'я', 'мне', 'моя', 'мой', 'люблю', 'хочу', 'возраст', 'рост'},
        'technical': {'код', 'api', 'баг', 'фикс', 'архитектура', 'python', 'titan', 'memory', 'plugin'},
        'temporal': {'завтра', 'сегодня', 'встреча', 'созвон', 'deadline', 'срочно', 'часов'},
        'plans': {'планируем', 'будем', 'собираемся', 'встретимся', 'сделаем'},
        'correction': {'нет', 'не так', 'ошибка', 'исправить', 'на самом деле'},
        'emotional': {'рада', 'счастлива', 'грустно', 'устала', 'обожаю', 'ненавижу', 'офигенно'}
    }
    
    def __init__(
        self,
        importance_threshold: float = 0.65,
        weights: Optional[ImportanceWeights] = None,
        model_name: str = "lightweight"
    ):
        self.importance_threshold = importance_threshold
        self.weights = weights or ImportanceWeights()
        logger.info(f"LightweightMLEvaluator initialized (no ML dependencies needed)")
    
    def evaluate(
        self,
        text: str,
        context: Optional[Dict] = None
    ) -> Tuple[bool, float, MemoryFeatures]:
        """Evaluate using keyword matching with ML-like scoring."""
        
        text_lower = text.lower()
        
        # Compute pseudo-ML scores
        scores = {}
        for category, keywords in self.IMPORTANCE_KEYWORDS.items():
            # Count matching keywords
            matches = sum(1 for kw in keywords if kw in text_lower)
            # Normalize by text length (simulate semantic density)
            word_count = len(text_lower.split())
            scores[category] = min(matches / max(word_count * 0.1, 1), 1.0)
        
        # Create features
        features = MemoryFeatures()
        features.is_personal = scores['personal'] > 0.3
        features.is_technical = scores['technical'] > 0.3
        features.has_temporal = scores['temporal'] > 0.2
        features.has_plans = scores['plans'] > 0.2
        features.is_correction = scores['correction'] > 0.4
        features.emotional_weight = scores['emotional']
        
        # Simple entity extraction
        features.entities = self._extract_entities(text)
        
        # Calculate importance
        importance = self._calculate_importance(features, scores)
        
        # Context overrides
        if context:
            if context.get('force_save'):
                importance = 1.0
            elif context.get('project') == 'titan':
                importance = max(importance, 0.7)
        
        should_save = importance >= self.importance_threshold
        
        logger.info(
            f"Lightweight evaluated: importance={importance:.2f}, "
            f"save={should_save}, text_preview='{text[:50]}...'"
        )
        
        return should_save, importance, features
    
    def _extract_entities(self, text: str) -> List[str]:
        """Extract potential entities."""
        entities = []
        words = text.split()
        
        # Capitalized words
        for word in words:
            if len(word) > 2 and word[0].isupper():
                entities.append(word)
        
        # Numbers with units
        import re
        pattern = r'\b\d+\s*(?:gb|mb|см|кг|км|часов?)\b'
        entities.extend(re.findall(pattern, text, re.I))
        
        return list(set(entities))[:10]
    
    def _calculate_importance(
        self,
        features: MemoryFeatures,
        scores: Dict[str, float]
    ) -> float:
        """Calculate weighted importance."""
        importance = 0.0
        
        importance += scores.get('personal', 0) * self.weights.personal
        importance += scores.get('technical', 0) * self.weights.technical
        importance += scores.get('temporal', 0) * self.weights.temporal
        importance += scores.get('plans', 0) * self.weights.plans
        importance += scores.get('emotional', 0) * self.weights.emotional
        importance += scores.get('correction', 0) * self.weights.correction
        
        # Normalize
        total_weight = sum([
            self.weights.personal,
            self.weights.technical,
            self.weights.temporal,
            self.weights.plans,
            self.weights.emotional,
            self.weights.correction
        ])
        
        return min(importance / total_weight, 1.0)
    
    def determine_priority(
        self,
        importance: float,
        features: MemoryFeatures
    ) -> StaticPriority:
        """Determine static priority."""
        if features.is_correction or (features.is_personal and importance > 0.8):
            return StaticPriority.HIGH
        elif (features.is_technical or features.has_temporal) and importance > 0.7:
            return StaticPriority.MEDIUM
        return StaticPriority.LOW


# Alias for compatibility
MLMemoryEvaluator = LightweightMLEvaluator
