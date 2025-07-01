"""Custom exceptions for Titan Event Bus."""


class EventBusError(Exception):
    """Base exception for Event Bus errors."""
    pass


class PublishError(EventBusError):
    """Error during event publishing."""
    pass


class ConsumerError(EventBusError):
    """Error in consumer processing."""
    pass


class DeadLetterError(EventBusError):
    """Error when moving event to dead letter queue."""
    pass


class ConfigurationError(EventBusError):
    """Configuration-related errors."""
    pass


class RateLimitError(EventBusError):
    """Rate limit exceeded."""
    pass
