"""Test configuration for Titan Event Bus."""

import pytest
import asyncio
import redis.asyncio as redis
from unittest.mock import AsyncMock, MagicMock

from titan_bus.config import EventBusConfig, StreamConfig


@pytest.fixture
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def test_config():
    """Test configuration."""
    return EventBusConfig(
        redis={"url": "redis://localhost:6379/15"},  # Use test DB
        streams=[
            StreamConfig(name="test.v1", maxlen=1000, rate_limit=10, retry_limit=2),
            StreamConfig(name="chat.v1", maxlen=5000, rate_limit=50, retry_limit=3)
        ],
        batch_size=10,
        block_timeout=100,
        consumer_group="test-group",
        max_global_rate=100
    )


@pytest.fixture
async def redis_client(test_config):
    """Redis client for testing."""
    client = redis.from_url(test_config.redis.url, decode_responses=False)
    
    # Clean test database
    await client.flushdb()
    
    yield client
    
    await client.flushdb()
    await client.close()


@pytest.fixture
def mock_redis():
    """Mock Redis client."""
    mock = AsyncMock(spec=redis.Redis)
    mock.ping = AsyncMock(return_value=True)
    mock.xadd = AsyncMock(return_value=b"1234567890-0")
    mock.xreadgroup = AsyncMock(return_value=[])
    mock.xack = AsyncMock(return_value=1)
    mock.xgroup_create = AsyncMock()
    return mock
