#!/bin/bash
# Smoke tests for Memory Service

set -e

echo "🧪 Starting Memory Service Smoke Tests..."
echo "======================================="

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test 1: Publish test message to chat.v1
echo -e "\n${YELLOW}Test 1: Publishing test message to chat.v1${NC}"
docker compose exec redis-master redis-cli -a titan_secret_2025 XADD chat.v1 \* \
    event_type user_message \
    payload '{"text":"Привет, я люблю котов и мой рост 162 см", "user_id":"test"}' \
    priority high

sleep 2
echo -e "${GREEN}✓ Message published${NC}"

# Test 2: Search for memory
echo -e "\n${YELLOW}Test 2: Searching for 'рост'${NC}"
curl -s -G http://localhost:8001/memory/search \
    --data-urlencode "q=рост" \
    --data-urlencode "k=5" | jq '.'

# Test 3: Test duplicate detection
echo -e "\n${YELLOW}Test 3: Publishing duplicate message${NC}"
docker compose exec redis-master redis-cli -a titan_secret_2025 XADD chat.v1 \* \
    event_type user_message \
    payload '{"text":"Привет, я люблю котов и мой рост 162 см", "user_id":"test"}' \
    priority high

sleep 2
echo -e "${GREEN}✓ Duplicate test completed (check logs)${NC}"

# Test 4: Correction
echo -e "\n${YELLOW}Test 4: Publishing correction${NC}"
docker compose exec redis-master redis-cli -a titan_secret_2025 XADD chat.v1 \* \
    event_type user_message \
    payload '{"text":"На самом деле мой рост 163 см", "user_id":"test"}' \
    priority high

sleep 2
echo -e "${GREEN}✓ Correction published${NC}"

# Test 5: Low importance message
echo -e "\n${YELLOW}Test 5: Publishing low importance message${NC}"
docker compose exec redis-master redis-cli -a titan_secret_2025 XADD chat.v1 \* \
    event_type user_message \
    payload '{"text":"Сегодня кот мурлыкал 10 минут", "user_id":"test"}' \
    priority low

sleep 2
echo -e "${GREEN}✓ Low importance test completed${NC}"

# Test 6: Manual GC trigger
echo -e "\n${YELLOW}Test 6: Triggering garbage collection${NC}"
curl -s -X POST http://localhost:8001/memory/gc | jq '.'

# Test 7: Check metrics
echo -e "\n${YELLOW}Test 7: Checking metrics${NC}"
curl -s http://localhost:8002/metrics | grep titan_memory | head -10

echo -e "\n${GREEN}🎉 All smoke tests completed!${NC}"
echo -e "Check memory service logs for details: ${YELLOW}make memory-logs${NC}"
