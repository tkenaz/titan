#!/bin/bash
# Stop all Titan services

echo "🛑 Stopping Titan services..."

# Stop services in reverse order
echo "🔌 Stopping Plugin Manager..."
docker compose -f docker-compose.plugins.yml down

echo "🧠 Stopping Memory Service..."
docker compose -f docker-compose.memory.yml down

echo "🔧 Stopping Event Bus..."
docker compose down

echo "📦 Stopping databases..."
docker compose -f docker-compose.databases.yml down

echo ""
echo "✅ All services stopped!"
echo ""
echo "💡 To clean up volumes: docker compose -f docker-compose.databases.yml down -v"
