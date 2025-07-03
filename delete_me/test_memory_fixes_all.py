#!/usr/bin/env python3
"""Test memory service fixes."""

import asyncio
import logging
import sys
from pathlib import Path

# Add project root to Python path
sys.path.insert(0, str(Path(__file__).parent))

from memory_service.models import EvaluationRequest
from memory_service.service import MemoryService
from memory_service.config import MemoryConfig
from memory_service.evaluator_ml import MLMemoryEvaluator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_memory_fixes():
    """Test all memory fixes."""
    
    # Load config
    config = MemoryConfig()
    
    # Initialize service
    service = MemoryService(config)
    await service.connect()
    
    try:
        # Test 1: ML Evaluator
        logger.info("=== Testing ML Evaluator ===")
        test_messages = [
            "Марина любит кофе по утрам",  # personal
            "Починили pgvector парсинг через register_vector",  # technical
            "Встреча завтра в 15:00",  # temporal
            "Я так рада что все работает!",  # emotional
            "Нет, не 0.3, а 0.65 threshold",  # correction
            "Привет, как дела?",  # low importance
        ]
        
        for msg in test_messages:
            req = EvaluationRequest(
                message=msg,
                source="test",
                context={"test": True}
            )
            resp = await service.evaluate_and_save(req)
            logger.info(f"Message: '{msg[:50]}...' -> Saved: {resp.saved}, Score: {resp.importance_score:.2f}")
        
        # Test 2: Vector Search
        logger.info("\n=== Testing Vector Search ===")
        search_req = await service.search("Марина кофе утро")
        logger.info(f"Found {len(search_req.results)} similar memories")
        for res in search_req.results[:3]:
            logger.info(f"  - {res.memory.summary[:60]}... (similarity: {res.similarity:.3f})")
        
        # Test 3: Duplicate Detection
        logger.info("\n=== Testing Duplicate Detection ===")
        dup_req = EvaluationRequest(
            message="Марина любит кофе по утрам",  # Same as first
            source="test"
        )
        dup_resp = await service.evaluate_and_save(dup_req)
        logger.info(f"Duplicate test: Saved={dup_resp.saved}, Reason={dup_resp.reason}")
        
        # Test 4: Force Save
        logger.info("\n=== Testing Force Save ===")
        force_req = EvaluationRequest(
            message="Это не очень важно, но надо запомнить",
            source="test",
            force_save=True
        )
        force_resp = await service.evaluate_and_save(force_req)
        logger.info(f"Force save: Saved={force_resp.saved}, Score={force_resp.importance_score}")
        
    finally:
        await service.disconnect()
    
    logger.info("\n✅ All tests completed!")


if __name__ == "__main__":
    asyncio.run(test_memory_fixes())
