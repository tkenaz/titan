"""Memory evaluation and feature extraction."""

import re
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime

from memory_service.models import (
    MemoryFeatures,
    ImportanceWeights,
    StaticPriority,
)


logger = logging.getLogger(__name__)


class FeatureExtractor:
    """Extract features from text for importance evaluation."""
    
    # Patterns for feature detection (case-insensitive)
    PERSONAL_PATTERNS = [
        r'\b(я|мне|меня|мой|моя|мое|мои|марина|marina)\b',
        r'\b(рост|вес|возраст|родилась?|живу|работаю)\b',
        r'\b(люблю|нравится|предпочитаю|хочу|мечтаю)\b',
    ]
    
    TECHNICAL_PATTERNS = [
        r'\b(код|api|функция|метод|класс|алгоритм|архитектура)\b',
        r'\b(python|javascript|react|docker|redis|postgresql)\b',
        r'\b(titan|event\s*bus|memory\s*service|plugin)\b',
    ]
    
    TEMPORAL_PATTERNS = [
        r'\b(сегодня|вчера|завтра|послезавтра)\b',
        r'\b(понедельник|вторник|среда|четверг|пятница|суббота|воскресенье)\b',
        r'\b\d{1,2}[:\-]\d{2}\b',  # Time
        r'\b\d{1,2}[\./]\d{1,2}[\./]\d{2,4}\b',  # Date
    ]
    
    EMOTIONAL_WORDS = {
        'positive': ['рада', 'счастлива', 'отлично', 'круто', 'люблю', 'обожаю', 'восторг'],
        'negative': ['грустно', 'плохо', 'устала', 'болит', 'ненавижу', 'бесит', 'раздражает'],
        'strong': ['очень', 'сильно', 'невероятно', 'ужасно', 'офигенно', 'охуенно']
    }
    
    URGENT_PATTERNS = [
        r'\b(срочно|важно|критично|асап|asap|немедленно)\b',
        r'\b(todo|задача|напоминание|не забыть)\b',
        r'\b(поменять|изменить|обновить|исправить)\b.*\b(доступ|пароль|права)\b',
    ]
    
    PLAN_PATTERNS = [
        r'\b(давай|планируем|встретимся|созвон|встреча|митинг)\b',
        r'\b(завтра|послезавтра|на следующей неделе|в понедельник)\b.*\b(часов?|утра|вечера)\b',
        r'\b\d{1,2}[:\-]\d{2}\b.*\b(встреча|созвон|митинг)\b',
        r'\b(буду|будем|собираюсь|планирую)\b',
    ]
    
    CORRECTION_PATTERNS = [
        r'\b(нет|не так|неправильно|ошибка|исправ[ьл]ю)\b',
        r'\b(на самом деле|вообще-то|точнее)\b',
        r'\b(был[аои]?\s+\d+.*теперь\s+\d+)\b',  # "было X теперь Y"
    ]
    
    def __init__(self):
        # Compile patterns for efficiency with IGNORECASE flag
        self.personal_regex = re.compile('|'.join(self.PERSONAL_PATTERNS), re.IGNORECASE)
        self.technical_regex = re.compile('|'.join(self.TECHNICAL_PATTERNS), re.IGNORECASE)
        self.temporal_regex = re.compile('|'.join(self.TEMPORAL_PATTERNS), re.IGNORECASE)
        self.urgent_regex = re.compile('|'.join(self.URGENT_PATTERNS), re.IGNORECASE)
        self.plan_regex = re.compile('|'.join(self.PLAN_PATTERNS), re.IGNORECASE)
        self.correction_regex = re.compile('|'.join(self.CORRECTION_PATTERNS), re.IGNORECASE)
    
    def extract(self, text: str, context: Optional[Dict] = None) -> MemoryFeatures:
        """Extract features from text."""
        text_lower = text.lower()
        
        features = MemoryFeatures()
        
        # Personal information
        features.is_personal = bool(self.personal_regex.search(text_lower))
        
        # Technical content
        features.is_technical = bool(self.technical_regex.search(text_lower))
        
        # Temporal references
        features.has_temporal = bool(self.temporal_regex.search(text_lower))
        
        # Plans detection
        features.has_plans = bool(self.plan_regex.search(text_lower))
        
        # Urgent/TODO detection
        is_urgent = bool(self.urgent_regex.search(text_lower))
        if context and context.get('urgent'):
            is_urgent = True
        
        # If urgent, boost importance
        if is_urgent:
            features.has_temporal = True  # Временной признак
            features.emotional_weight = max(features.emotional_weight, 0.8)  # Высокая важность
        
        # Emotional weight
        features.emotional_weight = self._calculate_emotional_weight(text_lower)
        
        # Corrections
        features.is_correction = bool(self.correction_regex.search(text_lower))
        if context and context.get('is_correction'):
            features.is_correction = True
        
        # Extract entities (simple version - in production use spaCy)
        features.entities = self._extract_entities(text)
        
        return features
    
    def _calculate_emotional_weight(self, text: str) -> float:
        """Calculate emotional weight of text."""
        weight = 0.0
        
        # Count emotional words
        for word in self.EMOTIONAL_WORDS['positive']:
            weight += text.count(word) * 0.3
        
        for word in self.EMOTIONAL_WORDS['negative']:
            weight += text.count(word) * 0.3
        
        for word in self.EMOTIONAL_WORDS['strong']:
            weight += text.count(word) * 0.2
        
        # Cap at 1.0
        return min(weight, 1.0)
    
    def _extract_entities(self, text: str) -> List[str]:
        """Extract named entities (simplified version)."""
        entities = []
        
        # Extract capitalized words (potential names)
        words = text.split()
        for i, word in enumerate(words):
            if word[0].isupper() and i > 0 and not words[i-1].endswith('.'):
                entities.append(word)
        
        # Extract numbers with units
        number_pattern = r'\b\d+\s*(см|кг|км|м|gb|mb|tb)\b'
        entities.extend(re.findall(number_pattern, text, re.I))
        
        # Extract emails
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        entities.extend(re.findall(email_pattern, text))
        
        return list(set(entities))  # Unique entities


class MemoryEvaluator:
    """Evaluate messages for memory storage."""
    
    def __init__(
        self,
        importance_threshold: float = 0.75,
        weights: Optional[ImportanceWeights] = None
    ):
        self.importance_threshold = importance_threshold
        self.weights = weights or ImportanceWeights()
        self.extractor = FeatureExtractor()
    
    def evaluate(
        self,
        text: str,
        context: Optional[Dict] = None
    ) -> Tuple[bool, float, MemoryFeatures]:
        """
        Evaluate if text should be stored in memory.
        
        Returns:
            (should_save, importance_score, features)
        """
        # Extract features
        features = self.extractor.extract(text, context)
        
        # Calculate importance score
        importance = self._calculate_importance(features)
        
        # Decision
        should_save = importance >= self.importance_threshold
        
        logger.info(
            f"Evaluated message: importance={importance:.2f}, "
            f"save={should_save}, features={features.model_dump()}"
        )
        
        return should_save, importance, features
    
    def _calculate_importance(self, features: MemoryFeatures) -> float:
        """
        Calculate importance score based on features.
        
        Formula: importance = 0.9·personal + 0.8·technical + 0.9·temporal
                            + 0.7·emotional + 1.0·correction
        """
        score = 0.0
        
        if features.is_personal:
            score += self.weights.personal
        
        if features.is_technical:
            score += self.weights.technical
        
        if features.has_temporal:
            score += self.weights.temporal
        
        if features.has_plans:
            score += self.weights.plans
        
        if features.emotional_weight > 0:
            score += self.weights.emotional * features.emotional_weight
        
        if features.is_correction:
            score += self.weights.correction
        
        # Normalize to [0, 1] range
        # Max possible score is sum of all weights
        max_score = (
            self.weights.personal +
            self.weights.technical +
            self.weights.temporal +
            self.weights.plans +
            self.weights.emotional +
            self.weights.correction
        )
        
        return min(score / max_score, 1.0)
    
    def determine_priority(
        self,
        importance: float,
        features: MemoryFeatures
    ) -> StaticPriority:
        """Determine static priority based on importance and features."""
        # Corrections and personal info get high priority
        if features.is_correction or (features.is_personal and importance > 0.8):
            return StaticPriority.HIGH
        
        # Technical info with high importance gets medium
        if features.is_technical and importance > 0.7:
            return StaticPriority.MEDIUM
        
        # Everything else is low
        return StaticPriority.LOW
