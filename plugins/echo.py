"""Echo plugin - simply echoes back the input."""

import logging
import json

logger = logging.getLogger(__name__)

# Plugin metadata
PLUGIN_METADATA = {
    'name': 'echo',
    'version': '1.0.0',
    'description': 'Simple echo plugin for testing'
}

# No Docker required
REQUIRES_DOCKER = False


def handle(event_data: dict, docker_client=None) -> dict:
    """Echo back the event data."""
    
    payload = event_data.get('payload', {})
    
    # Extract message
    message = payload.get('message', 'No message provided')
    
    # Simple echo
    response = {
        'echo': message,
        'original_event_type': event_data.get('event_type'),
        'processed_at': str(json.dumps(event_data, default=str))[:100] + '...'
    }
    
    logger.info(f"Echo plugin processed: {message[:50]}...")
    
    return response
