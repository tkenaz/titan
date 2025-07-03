"""Prometheus metrics for Memory Service."""

from prometheus_client import Counter, Histogram, Gauge, Info

# Info metrics
memory_service_info = Info(
    'memory_service_info',
    'Memory Service information'
)

# Counters
memories_saved_total = Counter(
    'memory_service_saved_total',
    'Total number of memories saved',
    ['priority', 'source']
)

memories_duplicates_total = Counter(
    'memory_service_duplicates_total', 
    'Total number of duplicate memories detected',
    ['source']
)

memories_evaluated_total = Counter(
    'memory_service_evaluated_total',
    'Total number of messages evaluated',
    ['saved', 'source']
)

searches_total = Counter(
    'memory_service_searches_total',
    'Total number of searches performed'
)

# Histograms
evaluation_duration = Histogram(
    'memory_service_evaluation_duration_seconds',
    'Time spent evaluating message importance'
)

embedding_duration = Histogram(
    'memory_service_embedding_duration_seconds',
    'Time spent generating embeddings',
    buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0]
)

search_duration = Histogram(
    'memory_service_search_duration_seconds',
    'Time spent searching memories'
)

# Gauges
memories_count = Gauge(
    'memory_service_memories_count',
    'Current number of memories in storage'
)

# Cost tracking
embedding_cost_total = Counter(
    'memory_service_embedding_cost_usd',
    'Total cost of embeddings in USD'
)

# Initialize info
memory_service_info.info({
    'version': '1.0.0',
    'embedding_model': 'text-embedding-3-small',
    'evaluator_model': 'multilingual-e5-large'
})
