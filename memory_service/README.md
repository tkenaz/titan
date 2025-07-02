# Titan Memory Service

Long-term and short-term memory for Titan, providing automatic extraction, storage, search, and "forgetting" of facts from dialogues and system events.

## Architecture

```
Event Bus → Memory Service → Vector DB (PostgreSQL + pgvector)
                         → Graph DB (Neo4j)
                         → Cache (Redis)
```

## Features

- **Automatic Memory Extraction**: Evaluates messages for importance
- **Duplicate Detection**: Prevents storing similar memories
- **Semantic Search**: Find memories by meaning, not just keywords
- **Graph Relationships**: Track connections between memories
- **Garbage Collection**: Automatically forget old, unused memories
- **Event Integration**: Listens to chat.v1 and system.v1 events

## Quick Start

```bash
# Start memory service with dependencies
make memory-up

# Check logs
make memory-logs

# Run tests
make memory-test

# Stop service
make memory-down
```

## API Endpoints

- `POST /memory/evaluate` - Evaluate and save message
- `GET /memory/search?q=...` - Search memories
- `POST /memory/remember` - Explicitly save memory
- `POST /memory/forget` - Delete memory
- `POST /memory/gc` - Run garbage collection
- `GET /metrics` - Prometheus metrics

API documentation: http://localhost:8001/docs

## Importance Algorithm

```
importance = 0.9·personal + 0.8·technical + 0.9·temporal
           + 0.7·emotional + 1.0·correction

save_if importance ≥ 0.75
```

## Memory Decay (Garbage Collection)

```
age = days_since(last_accessed)
decay = usage_count / (1 + age)
score = decay + emotional_weight

if static_priority != 'high' and score < 0.25:
    delete memory
```

## Configuration

Edit `config/memory.yaml`:

```yaml
importance_threshold: 0.75
gc_threshold: 0.25
embedding_model: text-embedding-3-small
```

## Test Coverage

Required test cases:
- MEM-01: New fact "Рост 162 см" → saved with high priority
- MEM-02: Duplicate "Рост 162 см" → not created
- MEM-03: Correction "Рост 163 см" → updates existing
- MEM-04: Low-value fact → not saved
- MEM-05: GC removes old memories with score < 0.25

Run tests: `make memory-test`

## Monitoring

- Grafana dashboards: http://localhost:3000
- Prometheus metrics: http://localhost:8002/metrics
- Neo4j browser: http://localhost:7474

## License

MIT
