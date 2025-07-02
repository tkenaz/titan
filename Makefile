.PHONY: help build up down test clean logs dev install lint format memory-up memory-down memory-test

# Default target
help:
	@echo "Titan Event Bus - Available commands:"
	@echo "  make build    - Build Docker images"
	@echo "  make up       - Start all services"
	@echo "  make down     - Stop all services"
	@echo "  make test     - Run tests"
	@echo "  make clean    - Clean up containers and volumes"
	@echo "  make logs     - Show logs"
	@echo "  make dev      - Start in development mode"
	@echo "  make install  - Install Python dependencies"
	@echo "  make lint     - Run linters"
	@echo "  make format   - Format code"
	@echo "  make memory-up    - Start memory service"
	@echo "  make memory-down  - Stop memory service"
	@echo "  make memory-test  - Test memory service"

# Build Docker images
build:
	docker compose build

# Start services
up:
	docker compose up -d
	@echo "Waiting for services to be ready..."
	@sleep 5
	@echo "Services started!"
	@echo "  - Grafana: http://localhost:3000 (admin/admin)"
	@echo "  - Prometheus: http://localhost:9090"
	@echo "  - Jaeger: http://localhost:16686"

# Stop services
down:
	docker compose down

# Run tests
test:
	docker compose run --rm titan-eventbus pytest -v --cov=titan_bus --cov-report=term-missing

# Clean up
clean:
	docker compose down -v
	rm -rf __pycache__ .pytest_cache .coverage
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete

# Show logs
logs:
	docker compose logs -f

# Development mode
dev:
	python -m venv venv
	./venv/bin/pip install -e ".[dev]"
	docker compose up -d redis-master redis-replica redis-sentinel
	./venv/bin/python -m titan_bus.server

# Install dependencies
install:
	pip install -e ".[dev]"

# Run linters
lint:
	ruff check titan_bus tests
	mypy titan_bus

# Format code
format:
	black titan_bus tests
	ruff check --fix titan_bus tests

# Quick test a single event
test-publish:
	@docker compose exec titan-eventbus python -c "\
	import asyncio; \
	from titan_bus import publish, EventPriority; \
	asyncio.run(publish('chat.v1', 'test_message', {'text': 'Hello Titan!'}, EventPriority.HIGH))"

# Monitor Redis streams
monitor:
	@docker compose exec redis-master redis-cli -a titan_secret_2025 monitor

# Check Redis stream contents
check-streams:
	@echo "=== Stream lengths ==="
	@docker compose exec redis-master redis-cli -a titan_secret_2025 XLEN chat.v1 || echo "chat.v1: 0"
	@docker compose exec redis-master redis-cli -a titan_secret_2025 XLEN fs.v1 || echo "fs.v1: 0"
	@docker compose exec redis-master redis-cli -a titan_secret_2025 XLEN system.v1 || echo "system.v1: 0"
	@docker compose exec redis-master redis-cli -a titan_secret_2025 XLEN plugin.v1 || echo "plugin.v1: 0"
# Memory Service commands
memory-up:
	docker compose -f docker-compose.yml -f docker-compose.memory.yml up -d
	@echo "Memory Service starting..."
	@echo "  - API: http://localhost:8001"
	@echo "  - Metrics: http://localhost:8002/metrics"
	@echo "  - Neo4j: http://localhost:7474 (neo4j/titan_neo4j_2025)"

memory-down:
	docker compose -f docker-compose.memory.yml down

memory-test:
	docker compose -f docker-compose.memory.yml run --rm memory-service pytest -v memory_service/tests/

memory-logs:
	docker compose -f docker-compose.memory.yml logs -f memory-service
