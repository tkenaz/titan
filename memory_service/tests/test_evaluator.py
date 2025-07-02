"""Tests for memory evaluation."""

import pytest

from memory_service.evaluator import FeatureExtractor, MemoryEvaluator
from memory_service.models import StaticPriority


class TestFeatureExtractor:
    """Test feature extraction."""
    
    def test_personal_detection(self):
        """Test detection of personal information."""
        extractor = FeatureExtractor()
        
        # Personal info
        features = extractor.extract("Мой рост 162 см")
        assert features.is_personal is True
        
        features = extractor.extract("Я живу в Харькове")
        assert features.is_personal is True
        
        # Not personal
        features = extractor.extract("Docker контейнер запущен")
        assert features.is_personal is False
    
    def test_technical_detection(self):
        """Test detection of technical content."""
        extractor = FeatureExtractor()
        
        # Technical
        features = extractor.extract("Создал новый API endpoint для Titan")
        assert features.is_technical is True
        
        features = extractor.extract("Python функция возвращает список")
        assert features.is_technical is True
        
        # Not technical
        features = extractor.extract("Сегодня хорошая погода")
        assert features.is_technical is False
    
    def test_temporal_detection(self):
        """Test detection of temporal references."""
        extractor = FeatureExtractor()
        
        # Temporal
        features = extractor.extract("Встреча завтра в 14:30")
        assert features.has_temporal is True
        
        features = extractor.extract("Это было в понедельник")
        assert features.has_temporal is True
        
        # Not temporal
        features = extractor.extract("Люблю кофе")
        assert features.has_temporal is False
    
    def test_correction_detection(self):
        """Test detection of corrections."""
        extractor = FeatureExtractor()
        
        # Corrections
        features = extractor.extract("Нет, мой рост не 162, а 163 см")
        assert features.is_correction is True
        
        features = extractor.extract("На самом деле это неправильно")
        assert features.is_correction is True
        
        # Not correction
        features = extractor.extract("Все работает отлично")
        assert features.is_correction is False
    
    def test_emotional_weight(self):
        """Test emotional weight calculation."""
        extractor = FeatureExtractor()
        
        # High emotion
        features = extractor.extract("Я очень рада! Это просто отлично!")
        assert features.emotional_weight > 0.5
        
        # Low emotion
        features = extractor.extract("Документация обновлена")
        assert features.emotional_weight < 0.2
    
    def test_entity_extraction(self):
        """Test entity extraction."""
        extractor = FeatureExtractor()
        
        features = extractor.extract("Марина работает в Titan, ее email marina@example.com")
        assert "marina@example.com" in features.entities
        assert any("Марина" in e or "Titan" in e for e in features.entities)


class TestMemoryEvaluator:
    """Test memory evaluation logic."""
    
    def test_importance_calculation(self):
        """Test importance score calculation."""
        evaluator = MemoryEvaluator(importance_threshold=0.75)
        
        # High importance - personal correction
        should_save, score, features = evaluator.evaluate(
            "Исправляю: мой рост 163 см, не 162"
        )
        assert should_save is True
        assert score > 0.75
        assert features.is_personal is True
        assert features.is_correction is True
    
    def test_low_importance_rejection(self):
        """Test rejection of low importance messages."""
        evaluator = MemoryEvaluator(importance_threshold=0.75)
        
        # Low importance
        should_save, score, features = evaluator.evaluate(
            "Окей"
        )
        assert should_save is False
        assert score < 0.75
    
    def test_priority_determination(self):
        """Test static priority assignment."""
        evaluator = MemoryEvaluator()
        
        # High priority - correction
        _, score, features = evaluator.evaluate("Нет, мой возраст 30, не 29")
        priority = evaluator.determine_priority(score, features)
        assert priority == StaticPriority.HIGH
        
        # Medium priority - technical
        _, score, features = evaluator.evaluate("Реализовал новый алгоритм сортировки")
        priority = evaluator.determine_priority(score, features)
        assert priority == StaticPriority.MEDIUM
        
        # Low priority
        _, score, features = evaluator.evaluate("Интересно")
        priority = evaluator.determine_priority(score, features)
        assert priority == StaticPriority.LOW
