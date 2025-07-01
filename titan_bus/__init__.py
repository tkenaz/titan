"""Titan Event Bus - Core event-driven infrastructure for Titan project."""

from titan_bus.client import EventBusClient, publish, subscribe, ack, replay
from titan_bus.event import Event, EventPriority, EventMeta
from titan_bus.processor import EventProcessor
from titan_bus.exceptions import (
    EventBusError,
    PublishError,
    ConsumerError,
    DeadLetterError,
)

__version__ = "0.1.0"

__all__ = [
    # Client API
    "EventBusClient",
    "publish",
    "subscribe",
    "ack",
    "replay",
    # Event models
    "Event",
    "EventPriority",
    "EventMeta",
    # Processor
    "EventProcessor",
    # Exceptions
    "EventBusError",
    "PublishError",
    "ConsumerError",
    "DeadLetterError",
]
