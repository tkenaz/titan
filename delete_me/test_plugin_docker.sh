#!/bin/bash
# Test Plugin Manager with Docker

echo "🐳 Plugin Manager Docker Test"
echo "============================"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Check if Redis is running
echo -e "\n${YELLOW}Checking Redis...${NC}"
if docker ps | grep -q "titan-redis"; then
    echo -e "${GREEN}✓ Redis is running${NC}"
else
    echo -e "${YELLOW}Starting Redis...${NC}"
    make up
    sleep 5
fi

# Build Plugin Manager image
echo -e "\n${YELLOW}Building Plugin Manager image...${NC}"
docker build -f plugin-manager.Dockerfile -t titan-plugin-manager:latest .

# Start Plugin Manager
echo -e "\n${YELLOW}Starting Plugin Manager...${NC}"
docker run -d \
    --name test-plugin-manager \
    --network host \
    -v $(pwd)/plugins:/app/plugins \
    -v $(pwd)/logs:/app/logs \
    -v $(pwd)/config:/app/config \
    -v /var/run/docker.sock:/var/run/docker.sock \
    -e PLUGIN_EVENT_BUS_URL=redis://:titan_secret_2025@localhost:6379/0 \
    titan-plugin-manager:latest

sleep 5

# Check health
echo -e "\n${YELLOW}Checking health...${NC}"
if curl -s http://localhost:8003/health | grep -q "healthy"; then
    echo -e "${GREEN}✓ Plugin Manager is healthy${NC}"
else
    echo -e "${RED}✗ Plugin Manager health check failed${NC}"
    docker logs test-plugin-manager
    exit 1
fi

# List plugins
echo -e "\n${YELLOW}Loaded plugins:${NC}"
curl -s http://localhost:8003/plugins | python -m json.tool

# Test shell_runner
echo -e "\n${YELLOW}Testing shell_runner plugin...${NC}"
RESPONSE=$(curl -s -X POST http://localhost:8003/plugins/trigger \
    -H "Content-Type: application/json" \
    -d '{
        "plugin_name": "shell_runner",
        "event_data": {
            "event_id": "docker-test-1",
            "topic": "system.v1",
            "event_type": "run_cmd",
            "payload": {"command": "uname -a"}
        }
    }')

echo "$RESPONSE" | python -m json.tool

# Test file_watcher
echo -e "\n${YELLOW}Testing file_watcher plugin...${NC}"
RESPONSE=$(curl -s -X POST http://localhost:8003/plugins/trigger \
    -H "Content-Type: application/json" \
    -d '{
        "plugin_name": "file_watcher",
        "event_data": {
            "event_id": "docker-test-2",
            "topic": "fs.v1",
            "event_type": "file_created",
            "payload": {
                "path": "/app/test_document.md",
                "mime_type": "text/markdown"
            }
        }
    }')

echo "$RESPONSE" | python -m json.tool

# Check logs
echo -e "\n${YELLOW}Recent logs:${NC}"
docker logs --tail 20 test-plugin-manager

# Cleanup
echo -e "\n${YELLOW}Cleaning up...${NC}"
docker stop test-plugin-manager
docker rm test-plugin-manager

echo -e "\n${GREEN}✓ Test complete!${NC}"
