#!/bin/bash
# Check which version of code is running in containers

echo "🔍 Checking code versions in containers..."
echo ""

# Check if memory/stats endpoint exists in running container
echo "1. Checking Memory Service container code:"
echo "   Looking for /memory/stats endpoint..."
docker exec titan-memory-service grep -n "memory/stats" /app/memory_service/api.py 2>/dev/null || echo "   ❌ Endpoint not found in container!"

echo ""
echo "2. Comparing local vs container files:"
echo "   Local file size:"
ls -la memory_service/api.py | awk '{print "   " $9 ": " $5 " bytes"}'

echo "   Container file size:"
docker exec titan-memory-service ls -la /app/memory_service/api.py 2>/dev/null | awk '{print "   " $9 ": " $5 " bytes"}' || echo "   ❌ Cannot check container file"

echo ""
echo "3. Container build time:"
docker inspect titan-memory-service | jq -r '.[0].Created' | xargs -I {} date -d {} "+   Built: %Y-%m-%d %H:%M:%S"

echo ""
echo "4. Rebuilding containers to ensure latest code..."
echo "   Run these commands:"
echo "   docker compose -f docker-compose.memory.yml down"
echo "   docker compose -f docker-compose.memory.yml build --no-cache"
echo "   docker compose -f docker-compose.memory.yml up -d"
