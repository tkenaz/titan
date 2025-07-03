"""ML-based Memory evaluation using e5-large-v2."""

import re
import logging
import asyncio
from typing import Dict, List, Optional, Tuple
from datetime import datetime

import torch
from sentence_transformers import SentenceTransformer
import numpy as np

from memory_service.models import (
    MemoryFeatures,
    ImportanceWeights,
    StaticPriority,
)

logger = logging.getLogger(__name__)


class MLMemoryEvaluator:
    """Evaluate messages using e5-large-v2 for semantic understanding."""
    
    # Semantic templates for importance categories
    IMPORTANCE_TEMPLATES = {
        'personal': [
            "This is personal information about the user",
            "User's preferences and characteristics",
            "Facts about Marina's life and personality",
            "Личная информация о пользователе",
            "Предпочтения и характеристики Марины"
        ],
        'technical': [
            "Technical implementation details",
            "Code architecture and design decisions",
            "Bug fixes and technical problems",
            "Технические детали реализации",
            "Архитектурные решения и код"
        ],
        'temporal': [
            "Time-sensitive information with deadlines",
            "Scheduled events and appointments",
            "Task with specific timing",
            "Информация со сроками выполнения",
            "Запланированные события и встречи"
        ],
        'plans': [
            "Future plans and intentions",
            "Upcoming meetings and tasks",
            "Project roadmap and milestones",
            "Будущие планы и намерения",
            "Предстоящие встречи и задачи"
        ],
        'correction': [
            "Correction of previous information",
            "Updated facts replacing old ones",
            "Error fixes and clarifications",
            "Исправление предыдущей информации",
            "Обновленные факты взамен старых"
        ],
        'emotional': [
            "Emotionally charged content",
            "Strong feelings and reactions",
            "Personal emotional state",
            "Эмоционально окрашенный контент",
            "Сильные чувства и реакции"
        ]
    }
    
    # Entity extraction patterns (keep these for efficiency)
    ENTITY_PATTERNS = {
        'email': r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
        'url': r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+',
        'path': r'/[A-Za-z0-9/_\-\.]+',
        'number_with_unit': r'\b\d+\s*(см|кг|км|м|gb|mb|tb|ms|s)\b',
        'time': r'\b\d{1,2}[:\-]\d{2}\b',
        'date': r'\b\d{1,2}[\./]\d{1,2}[\./]\d{2,4}\b'
    }
    
    def __init__(
        self,
        importance_threshold: float = 0.65,
        weights: Optional[ImportanceWeights] = None,
        model_name: str = "intfloat/multilingual-e5-large"
    ):
        self.importance_threshold = importance_threshold
        self.weights = weights or ImportanceWeights()
        
        # Initialize model with MPS support for M3 Max
        logger.info(f"Loading {model_name}...")
        self.device = "mps" if torch.backends.mps.is_available() else "cpu"
        self.model = SentenceTransformer(model_name, device=self.device)
        
        # Pre-compute template embeddings
        logger.info("Computing template embeddings...")
        self.template_embeddings = {}
        for category, templates in self.IMPORTANCE_TEMPLATES.items():
            # Add "query: " prefix for e5 models
            prefixed_templates = [f"query: {t}" for t in templates]
            embeddings = self.model.encode(
                prefixed_templates,
                convert_to_tensor=True,
                show_progress_bar=False
            )
            self.template_embeddings[category] = embeddings
        
        # Compile regex patterns
        self.entity_regexes = {
            name: re.compile(pattern, re.IGNORECASE)
            for name, pattern in self.ENTITY_PATTERNS.items()
        }
        
        logger.info(f"MLMemoryEvaluator initialized on {self.device}")
    
    def evaluate(
        self,
        text: str,
        context: Optional[Dict] = None
    ) -> Tuple[bool, float, MemoryFeatures]:
        """
        Evaluate if text should be stored in memory using ML.
        
        Returns:
            (should_save, importance_score, features)
        """
        # Compute features synchronously (model is fast on M3 Max)
        features, scores = self._compute_features(text, context)
        
        # Calculate importance score
        importance = self._calculate_importance(features, scores)
        
        # Override for certain contexts
        if context:
            if context.get('force_save'):
                importance = 1.0
            elif context.get('project') == 'titan':
                importance = max(importance, 0.7)
            elif context.get('urgent'):
                importance = max(importance, 0.8)
        
        # Decision
        should_save = importance >= self.importance_threshold
        
        logger.info(
            f"ML Evaluated: importance={importance:.2f}, "
            f"save={should_save}, scores={scores}"
        )
        
        return should_save, importance, features
    
    def _compute_features(
        self,
        text: str,
        context: Optional[Dict]
    ) -> Tuple[MemoryFeatures, Dict[str, float]]:
        """Compute features using ML model."""
        # Encode the text with "passage: " prefix for e5
        text_embedding = self.model.encode(
            f"passage: {text}",
            convert_to_tensor=True,
            show_progress_bar=False
        )
        
        # Compute similarities with each category
        scores = {}
        for category, template_embeds in self.template_embeddings.items():
            similarities = torch.nn.functional.cosine_similarity(
                text_embedding.unsqueeze(0),
                template_embeds
            )
            scores[category] = float(similarities.max())
        
        # Create features based on scores
        features = MemoryFeatures()
        
        # Thresholds for each category
        features.is_personal = scores['personal'] > 0.65
        features.is_technical = scores['technical'] > 0.65
        features.has_temporal = scores['temporal'] > 0.6
        features.has_plans = scores['plans'] > 0.6
        features.is_correction = scores['correction'] > 0.7
        features.emotional_weight = min(scores['emotional'], 1.0)
        
        # Extract entities using regex (fast)
        features.entities = self._extract_entities(text)
        
        # Add context overrides
        if context:
            if context.get('is_correction'):
                features.is_correction = True
            if context.get('urgent'):
                features.has_temporal = True
        
        return features, scores
    
    def _extract_entities(self, text: str) -> List[str]:
        """Extract named entities using patterns."""
        entities = []
        
        for name, regex in self.entity_regexes.items():
            matches = regex.findall(text)
            entities.extend(matches)
        
        # Also extract capitalized words as potential names
        words = text.split()
        for i, word in enumerate(words):
            if (len(word) > 2 and 
                word[0].isupper() and 
                i > 0 and 
                not words[i-1].endswith('.')):
                entities.append(word)
        
        return list(set(entities))[:10]  # Max 10 unique entities
    
    def _calculate_importance(
        self,
        features: MemoryFeatures,
        scores: Dict[str, float]
    ) -> float:
        """Calculate importance using both features and raw scores."""
        # Use weighted combination of scores
        importance = 0.0
        
        importance += scores['personal'] * self.weights.personal
        importance += scores['technical'] * self.weights.technical
        importance += scores['temporal'] * self.weights.temporal
        importance += scores['plans'] * self.weights.plans
        importance += scores['emotional'] * self.weights.emotional
        importance += scores['correction'] * self.weights.correction
        
        # Normalize by sum of weights
        total_weight = sum([
            self.weights.personal,
            self.weights.technical,
            self.weights.temporal,
            self.weights.plans,
            self.weights.emotional,
            self.weights.correction
        ])
        
        normalized = importance / total_weight
        
        # Boost for multiple high scores
        high_score_count = sum(1 for s in scores.values() if s > 0.7)
        if high_score_count >= 2:
            normalized = min(normalized * 1.2, 1.0)
        
        return normalized
    
    def determine_priority(
        self,
        importance: float,
        features: MemoryFeatures
    ) -> StaticPriority:
        """Determine static priority based on importance and features."""
        # Corrections always get high priority
        if features.is_correction:
            return StaticPriority.HIGH
        
        # Personal + high importance = high priority
        if features.is_personal and importance > 0.8:
            return StaticPriority.HIGH
        
        # Technical or temporal with good importance = medium
        if (features.is_technical or features.has_temporal) and importance > 0.7:
            return StaticPriority.MEDIUM
        
        # Everything else is low
        return StaticPriority.LOW
