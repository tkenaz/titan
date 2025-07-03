#!/bin/bash
# Quick fix to start Goal Scheduler

echo "🎯 Starting Goal Scheduler..."

# First check if databases are running
if ! docker ps | grep -q titan-postgres; then
    echo "⚠️  Databases not running. Starting them first..."
    docker compose -f docker-compose.databases.yml up -d
    sleep 5
fi

# Check if main services are running
if ! docker ps | grep -q titan-redis-master; then
    echo "⚠️  Main services not running. Starting them..."
    docker compose up -d
    sleep 5
fi

# Now start Goal Scheduler
echo "📦 Building Goal Scheduler..."
docker compose -f docker-compose.yml -f docker-compose.scheduler.yml build

echo "🚀 Starting Goal Scheduler..."
docker compose -f docker-compose.yml -f docker-compose.scheduler.yml up -d

# Wait a bit
sleep 10

# Check if it's running
echo ""
echo "Checking Goal Scheduler status..."
if curl -s http://localhost:8005/health | grep -q "healthy"; then
    echo "✅ Goal Scheduler is now running!"
else
    echo "❌ Goal Scheduler failed to start"
    echo ""
    echo "Checking logs..."
    docker compose -f docker-compose.scheduler.yml logs --tail=50 goal-scheduler
fi
