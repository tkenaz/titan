#!/bin/bash
# Fix Goal Scheduler connection issues

echo "🔧 Fixing Goal Scheduler..."

# 1. Stop everything
echo "Stopping all services..."
docker compose -f docker-compose.yml down
docker compose -f docker-compose.databases.yml down
docker compose -f docker-compose.memory.yml down
docker compose -f docker-compose.plugins.yml down
docker compose -f docker-compose.scheduler.yml down

# 2. Remove orphan containers
docker container prune -f

# 3. Start only what we need for Goal Scheduler
echo "Starting core services..."
docker compose -f docker-compose.yml up -d

# Wait for Redis
echo "Waiting for Redis..."
sleep 5

# 4. Test Redis connection from host
echo "Testing Redis connection..."
docker exec titan-redis-master redis-cli ping

# 5. Build and run Goal Scheduler with correct ENV
echo "Building Goal Scheduler..."
docker compose -f docker-compose.scheduler.yml build

# 6. Run with explicit ENV override to ensure it uses the right Redis
echo "Starting Goal Scheduler with correct Redis URL..."
docker run -d \
  --name titan-goal-scheduler-temp \
  --network titan_default \
  -p 8005:8005 \
  -p 8006:8006 \
  -e SCHEDULER_REDIS_URL=redis://titan-redis-master:6379/2 \
  -e EVENT_BUS_URL=redis://titan-redis-master:6379/0 \
  -e ADMIN_TOKEN=${ADMIN_TOKEN:-titan-secret-token-change-me-in-production} \
  -v $(pwd)/goals:/app/goals \
  titan-goal-scheduler:latest

# 7. Check logs
echo "Checking logs..."
sleep 5
docker logs titan-goal-scheduler-temp --tail=20

# 8. Test health
echo "Testing health endpoint..."
curl http://localhost:8005/health
