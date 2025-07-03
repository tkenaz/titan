# Titan Testing Guide

## Quick Start

1. **Start all services:**
   ```bash
   chmod +x start_services.sh stop_services.sh
   ./start_services.sh
   ```

2. **Run tests:**
   ```bash
   python test_circuit_breaker.py
   ```

3. **Stop all services:**
   ```bash
   ./stop_services.sh
   ```

## Service Architecture

Titan uses multiple Docker Compose files:

- `docker-compose.databases.yml` - PostgreSQL, Neo4j, Redis
- `docker-compose.yml` - Event Bus (Redis Sentinel, Prometheus, Grafana)
- `docker-compose.memory.yml` - Memory Service (port 8001)
- `docker-compose.plugins.yml` - Plugin Manager (port 8003)

## Testing Issues & Solutions

### API Authentication Test Failures

**Problem:** Tests return 404 instead of 401/403  
**Причина:** Services not running or wrong ports

**Solution:**
1. Ensure all services are running: `./start_services.sh`
2. Check service health:
   ```bash
   curl http://localhost:8001/health  # Memory Service
   curl http://localhost:8003/health  # Plugin Manager
   ```

### Circuit Breaker Issues

**Problem:** Success rate calculation includes disabled state attempts  
**Solution:** Already fixed in code - only counts active executions

### Memory Service Issues

**Current Known Issues:**
1. **pgvector parsing** - asyncpg returns vectors in unexpected format
   - Temporary fix: Vector search disabled, using ORDER BY created_at
   - TODO: Fix vector parsing in storage.py

2. **Evaluator using regex** - Not semantic, just keyword matching
   - Temporary fix: Lowered threshold to 0.3
   - TODO: Integrate ML model (e5-large or similar)

## Environment Variables

Create `.env` file:
```bash
ADMIN_TOKEN=titan-secret-token-change-me-in-production
OPENAI_API_KEY=your-key-here
POSTGRES_PASSWORD=Frfgekmrj391
NEO4J_PASSWORD=Frfgekmrj391
```

## Debugging

View logs:
```bash
docker compose logs -f memory-service
docker compose logs -f plugin-manager
docker compose logs -f titan-eventbus
```

Check Redis streams:
```bash
docker exec titan-redis redis-cli
> XLEN chat.v1
> XREAD STREAMS chat.v1 0
```

## Make Commands

```bash
make all-up        # Start everything
make all-down      # Stop everything
make memory-logs   # View memory service logs
make plugins-logs  # View plugin manager logs
```
