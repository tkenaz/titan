#!/bin/bash
# Start all Titan services for testing

echo "🚀 Starting Titan services..."

# Start databases first
echo "📦 Starting databases (PostgreSQL, Neo4j, Redis)..."
docker compose -f docker-compose.databases.yml up -d

# Wait for databases to be ready
echo "⏳ Waiting for databases..."
sleep 10

# Start main services
echo "🔧 Starting Event Bus..."
docker compose up -d

# Start Memory Service
echo "🧠 Starting Memory Service..."
docker compose -f docker-compose.yml -f docker-compose.memory.yml up -d

# Start Plugin Manager
echo "🔌 Starting Plugin Manager..."
docker compose -f docker-compose.yml -f docker-compose.plugins.yml up -d

# Start Goal Scheduler
echo "🎯 Starting Goal Scheduler..."
docker compose -f docker-compose.yml -f docker-compose.scheduler.yml up -d

# Wait for all services
echo "⏳ Waiting for all services to be ready..."
sleep 15

# Check service health
echo ""
echo "✅ Service Status:"
echo "  - PostgreSQL: $(docker exec titan-postgres pg_isready -U postgres 2>&1 | grep -q "accepting connections" && echo "✅ Ready" || echo "❌ Not ready")"
echo "  - Neo4j: $(curl -s http://localhost:7474 > /dev/null 2>&1 && echo "✅ Ready" || echo "❌ Not ready")"
# Check multiple Redis instances
echo "  - Redis (Main): $(docker exec titan-redis redis-cli ping 2>&1 | grep -q "PONG" && echo "✅ Ready" || echo "❌ Not ready")"
echo "  - Redis (Master): $(docker exec titan-redis-master redis-cli ping 2>&1 | grep -q "PONG" && echo "✅ Ready" || echo "❌ Not ready")"
echo "  - Redis (DBS): $(docker exec titan-redis-dbs redis-cli ping 2>&1 | grep -q "PONG" && echo "✅ Ready" || echo "❌ Not ready")"
echo "  - Memory API: $(curl -s http://localhost:8001/health 2>&1 | grep -q "healthy" && echo "✅ Ready" || echo "❌ Not ready")"
echo "  - Plugin API: $(curl -s http://localhost:8003/health 2>&1 | grep -q "healthy" && echo "✅ Ready" || echo "❌ Not ready")"
echo "  - Goal Scheduler: $(curl -s http://localhost:8005/health 2>&1 | grep -q "healthy" && echo "✅ Ready" || echo "❌ Not ready")"

echo ""
echo "🎉 All services started! You can now run tests."
echo ""
echo "📝 Quick commands:"
echo "  - Run tests: python test_circuit_breaker_fixed.py"
echo "  - Test goals: python test_goal_scheduler.py"
echo "  - Manage goals: python titan-goals.py --help"
echo "  - View logs: docker compose logs -f"
echo "  - Stop all: ./stop_services.sh"
