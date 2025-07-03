"""Test plugin for Circuit Breaker testing."""

import random
import logging

logger = logging.getLogger(__name__)

# Plugin metadata
PLUGIN_METADATA = {
    'name': 'test_plugin',
    'version': '1.0.0',
    'description': 'Test plugin for circuit breaker'
}

# Plugin configuration
REQUIRES_DOCKER = False


def handle(event_data: dict, docker_client=None) -> dict:
    """Handle test events."""
    
    # Check if we should force an error
    if event_data.get('payload', {}).get('force_error'):
        logger.error("Forced error for testing")
        raise Exception("Test error - circuit breaker testing")
    
    # Random failure for chaos testing
    if event_data.get('payload', {}).get('chaos_mode'):
        if random.random() < 0.3:  # 30% failure rate
            raise Exception("Random chaos failure")
    
    # Normal execution
    message = event_data.get('payload', {}).get('message', 'Hello')
    result = f"Processed: {message}"
    
    logger.info(f"Test plugin executed successfully: {result}")
    
    return {
        'status': 'success',
        'result': result,
        'plugin': 'test_plugin'
    }
