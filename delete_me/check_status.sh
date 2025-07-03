#!/bin/bash
# Check status of all Titan services

echo "🔍 Checking all Titan containers..."
echo ""

# List all running containers with titan prefix
echo "📦 Running containers:"
docker ps --filter "name=titan" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

echo ""
echo "🔍 Checking Redis instances:"
for container in titan-redis titan-redis-master titan-redis-dbs titan-redis-replica; do
    if docker ps -q -f name=$container > /dev/null 2>&1; then
        echo -n "  - $container: "
        docker exec $container redis-cli ping 2>&1 || echo "Not responding"
    else
        echo "  - $container: Not running"
    fi
done

echo ""
echo "🔍 Checking service health endpoints:"
echo "  - Memory API: $(curl -s http://localhost:8001/health | jq -r '.status' 2>/dev/null || echo 'Not available')"
echo "  - Plugin API: $(curl -s http://localhost:8003/health | jq -r '.status' 2>/dev/null || echo 'Not available')"

echo ""
echo "🔍 Checking Redis connectivity from host:"
echo -n "  - localhost:6379: "
redis-cli -h localhost -p 6379 ping 2>/dev/null || echo "Not accessible"
echo -n "  - localhost:6380: "
redis-cli -h localhost -p 6380 ping 2>/dev/null || echo "Not accessible"

echo ""
echo "📊 Docker compose status:"
docker compose ps
