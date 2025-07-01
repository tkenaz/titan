"""Main server entry point for Titan Event Bus."""

import asyncio
import logging
import os
import signal
import sys
from pathlib import Path

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from titan_bus.client import EventBusClient
from titan_bus.config import EventBusConfig


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("/app/logs/eventbus.log", mode="a")
    ]
)
logger = logging.getLogger(__name__)


def setup_tracing():
    """Setup OpenTelemetry tracing."""
    resource = Resource(attributes={
        "service.name": "titan-eventbus",
        "service.version": "0.1.0"
    })
    
    provider = TracerProvider(resource=resource)
    
    # Configure OTLP exporter
    otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    if otlp_endpoint:
        processor = BatchSpanProcessor(
            OTLPSpanExporter(endpoint=otlp_endpoint)
        )
        provider.add_span_processor(processor)
        logger.info(f"Tracing enabled with OTLP endpoint: {otlp_endpoint}")
    
    trace.set_tracer_provider(provider)


async def example_handlers():
    """Example handlers for testing."""
    
    async def chat_handler(event):
        logger.info(f"Chat handler received: {event.event_type} - {event.payload}")
        # Simulate processing
        await asyncio.sleep(0.1)
    
    async def file_handler(event):
        logger.info(f"File handler received: {event.event_type} - {event.payload}")
        # Simulate processing
        await asyncio.sleep(0.05)
    
    return {
        "chat.v1": [chat_handler],
        "fs.v1": [file_handler]
    }


async def main():
    """Main server entry point."""
    logger.info("Starting Titan Event Bus Server")
    
    # Setup tracing
    setup_tracing()
    
    # Load configuration
    config_path = os.getenv("TITAN_CONFIG_PATH", "/app/config/eventbus.yaml")
    if Path(config_path).exists():
        config = EventBusConfig.from_yaml(config_path)
        logger.info(f"Loaded configuration from {config_path}")
    else:
        config = EventBusConfig()
        logger.warning("Using default configuration")
    
    # Create client
    client = EventBusClient(config)
    
    try:
        # Connect
        await client.connect()
        
        # Register example handlers (remove in production)
        handlers = await example_handlers()
        for topic, topic_handlers in handlers.items():
            for handler in topic_handlers:
                client.subscribe(topic, handler)
        
        # Start processor
        await client.start_processor()
        
        # Setup signal handlers
        stop_event = asyncio.Event()
        
        def signal_handler(sig, frame):
            logger.info(f"Received signal {sig}")
            stop_event.set()
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        logger.info("Event Bus Server running. Press Ctrl+C to stop.")
        
        # Wait for stop signal
        await stop_event.wait()
        
    except Exception as e:
        logger.error(f"Server error: {e}", exc_info=True)
        sys.exit(1)
    
    finally:
        # Cleanup
        logger.info("Shutting down Event Bus Server")
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
