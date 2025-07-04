"""
Tests for Model Gateway
"""
import pytest
import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import json

import sys
sys.path.append('/Users/mvyshhnyvetska/Desktop/titan')

from model_gateway.config import GatewayConfig, ModelConfig
from model_gateway.router import ModelRouter
from model_gateway.cost_tracker import CostTracker, BudgetGuard
from model_gateway.security import HMACValidator
from model_gateway.events import EventLogger


@pytest.fixture
def sample_config():
    """Sample gateway configuration"""
    return GatewayConfig(
        models={
            "gpt-4o": ModelConfig(
                provider="openai",
                engine="gpt-4o",
                input_cost=0.0000025,
                output_cost=0.00001,
                max_tokens=8192
            ),
            "o3-pro": ModelConfig(
                provider="openai",
                engine="o3-pro",
                input_cost=0.00002,
                output_cost=0.00008,
                max_tokens=4096
            )
        }
    )


@pytest.fixture
def mock_redis():
    """Mock Redis client"""
    redis = AsyncMock()
    redis.hget = AsyncMock(return_value=b"5.0")  # $5 spent
    redis.hgetall = AsyncMock(return_value={
        b"total": b"5.0",
        b"model:gpt-4o": b"3.0",
        b"model:o3-pro": b"2.0",
        b"prompt_tokens": b"10000",
        b"completion_tokens": b"5000"
    })
    redis.pipeline = MagicMock(return_value=AsyncMock())
    return redis


class TestCostTracker:
    """Test cost tracking functionality"""
    
    @pytest.mark.asyncio
    async def test_add_cost(self, mock_redis):
        """Test adding cost to tracker"""
        tracker = CostTracker(mock_redis, daily_limit_usd=20.0)
        
        # Mock pipeline
        pipe = AsyncMock()
        pipe.execute = AsyncMock(return_value=[10.5])  # New total
        mock_redis.pipeline.return_value = pipe
        
        result = await tracker.add_cost(
            model="gpt-4o",
            prompt_tokens=1000,
            completion_tokens=500,
            input_cost_per_token=0.0000025,
            output_cost_per_token=0.00001,
            trace_id="test-123"
        )
        
        assert result["input_cost"] == 0.0025
        assert result["output_cost"] == 0.005
        assert result["total_cost"] == 0.0075
        assert result["daily_total"] == 10.5
        assert result["budget_remaining"] == 9.5
    
    @pytest.mark.asyncio
    async def test_check_budget(self, mock_redis):
        """Test budget checking"""
        tracker = CostTracker(mock_redis, daily_limit_usd=20.0)
        
        # Under budget
        mock_redis.hget.return_value = b"15.0"
        allowed, stats = await tracker.check_budget()
        assert allowed is True
        assert stats["budget_remaining"] == 5.0
        
        # Over budget
        mock_redis.hget.return_value = b"25.0"
        allowed, stats = await tracker.check_budget()
        assert allowed is False
        assert stats["budget_remaining"] == -5.0


class TestBudgetGuard:
    """Test budget guard functionality"""
    
    @pytest.mark.asyncio
    async def test_hard_stop(self, mock_redis):
        """Test hard stop when budget exceeded"""
        tracker = CostTracker(mock_redis, daily_limit_usd=20.0)
        guard = BudgetGuard(tracker, hard_stop=True)
        
        # Simulate over budget
        mock_redis.hget.return_value = b"25.0"
        
        allowed, reason, stats = await guard.check_request_allowed()
        assert allowed is False
        assert "budget exceeded" in reason.lower()
    
    @pytest.mark.asyncio
    async def test_warning_threshold(self, mock_redis):
        """Test warning at threshold"""
        tracker = CostTracker(mock_redis, daily_limit_usd=20.0)
        guard = BudgetGuard(tracker, warning_threshold=0.8)
        
        # At 85% of budget
        mock_redis.hget.return_value = b"17.0"
        
        allowed, reason, stats = await guard.check_request_allowed()
        assert allowed is True
        assert "warning" in stats


class TestHMACValidator:
    """Test HMAC validation"""
    
    def test_sign_and_verify(self):
        """Test signing and verification"""
        validator = HMACValidator("secret-key")
        
        data = "Hello, World!"
        signature = validator.sign(data)
        
        assert validator.verify(data, signature) is True
        assert validator.verify(data + "tampered", signature) is False
    
    def test_stream_chunk_signing(self):
        """Test streaming chunk signatures"""
        validator = HMACValidator("secret-key")
        
        chunk = "This is a chunk"
        seq = 42
        signature = validator.sign_stream_chunk(chunk, seq)
        
        # Verify by reconstructing the data
        expected_data = json.dumps({"chunk": chunk, "seq": seq}, separators=(',', ':'))
        assert validator.verify(expected_data, signature) is True


class TestModelRouter:
    """Test model routing"""
    
    @pytest.mark.asyncio
    async def test_route_completion(self, sample_config, mock_redis):
        """Test routing completion request"""
        # Mock components
        cost_tracker = CostTracker(mock_redis, daily_limit_usd=20.0)
        event_logger = EventLogger(mock_redis)
        
        # Create router
        router = ModelRouter(
            config=sample_config,
            cost_tracker=cost_tracker,
            event_logger=event_logger,
            hmac_secret="test-secret"
        )
        
        # Mock provider
        mock_provider = AsyncMock()
        mock_provider.complete = AsyncMock(return_value=(
            "Hello from AI!",
            {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
        ))
        router.providers["openai"] = mock_provider
        
        # Mock pipeline for cost tracking
        pipe = AsyncMock()
        pipe.execute = AsyncMock(return_value=[5.0])  # Current total
        mock_redis.pipeline.return_value = pipe
        
        # Make request
        result = await router.route_completion(
            model_name="gpt-4o",
            messages=[{"role": "user", "content": "Hello"}],
            stream=False
        )
        
        assert result["content"] == "Hello from AI!"
        assert result["usage"]["total_tokens"] == 15
        assert "signature" in result
        assert "trace_id" in result
    
    @pytest.mark.asyncio
    async def test_unknown_model(self, sample_config, mock_redis):
        """Test handling unknown model"""
        router = ModelRouter(
            config=sample_config,
            cost_tracker=CostTracker(mock_redis),
            event_logger=EventLogger(mock_redis),
            hmac_secret="test-secret"
        )
        
        result = await router.route_completion(
            model_name="unknown-model",
            messages=[{"role": "user", "content": "Hello"}]
        )
        
        assert "error" in result
        assert result["status"] == 404
    
    @pytest.mark.asyncio
    async def test_budget_exceeded_response(self, sample_config, mock_redis):
        """Test response when budget exceeded"""
        # Set high spent amount
        mock_redis.hget.return_value = b"25.0"  # Over $20 limit
        
        router = ModelRouter(
            config=sample_config,
            cost_tracker=CostTracker(mock_redis, daily_limit_usd=20.0),
            event_logger=EventLogger(mock_redis),
            hmac_secret="test-secret"
        )
        
        result = await router.route_completion(
            model_name="gpt-4o",
            messages=[{"role": "user", "content": "Hello"}]
        )
        
        assert "error" in result
        assert result["status"] == 429
        assert "budget_stats" in result


# Integration test
@pytest.mark.asyncio
async def test_integration_mg01_proxy_stream():
    """MG-01: Test proxy call with streaming"""
    # This would require a full FastAPI test client
    # Placeholder for integration test
    pass


@pytest.mark.asyncio
async def test_integration_mg02_budget_exceeded():
    """MG-02: Test budget exceeded returns 429"""
    # This would require a full FastAPI test client
    # Placeholder for integration test
    pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
