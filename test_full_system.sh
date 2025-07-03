#!/bin/bash
# Comprehensive test of all Titan components

echo "🚀 TITAN FULL SYSTEM TEST"
echo "========================"
echo ""

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if services are running
echo "1️⃣ Checking services..."
echo ""

check_service() {
    local name=$1
    local url=$2
    
    if curl -s $url | grep -q "healthy"; then
        echo -e "   ${GREEN}✅ $name is running${NC}"
        return 0
    else
        echo -e "   ${RED}❌ $name is not running${NC}"
        return 1
    fi
}

all_running=true
check_service "Memory Service" "http://localhost:8001/health" || all_running=false
check_service "Plugin Manager" "http://localhost:8003/health" || all_running=false
check_service "Goal Scheduler" "http://localhost:8005/health" || all_running=false

if [ "$all_running" = false ]; then
    echo ""
    echo -e "${YELLOW}⚠️  Some services are not running!${NC}"
    echo "   Run: ./start_services.sh"
    exit 1
fi

echo ""
echo "2️⃣ Running component tests..."
echo ""

# Test Circuit Breaker
echo "Testing Plugin Manager (Circuit Breaker)..."
echo "1" | python test_circuit_breaker_fixed.py > /tmp/cb_test.log 2>&1
if grep -q "Circuit breaker test completed!" /tmp/cb_test.log; then
    echo -e "   ${GREEN}✅ Plugin Manager tests passed${NC}"
else
    echo -e "   ${RED}❌ Plugin Manager tests failed${NC}"
    echo "   Check: /tmp/cb_test.log"
fi

# Test Goal Scheduler
echo ""
echo "Testing Goal Scheduler..."
python test_goal_scheduler.py > /tmp/gs_test.log 2>&1
if grep -q "Goal Scheduler test completed!" /tmp/gs_test.log; then
    echo -e "   ${GREEN}✅ Goal Scheduler tests passed${NC}"
else
    echo -e "   ${RED}❌ Goal Scheduler tests failed${NC}"
    echo "   Check: /tmp/gs_test.log"
fi

# Test Integration
echo ""
echo "3️⃣ Testing integration between components..."
echo ""

# Create a test that uses all components
cat > /tmp/integration_test.py << 'EOF'
import asyncio
import httpx
import os
import time

async def test_integration():
    token = os.getenv("ADMIN_TOKEN", "titan-secret-token-change-me-in-production")
    headers = {"Authorization": f"Bearer {token}"}
    
    print("🔗 Testing component integration...")
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        # 1. Save something to memory
        print("\n1. Testing Memory Service...")
        memory_data = {
            "text": f"Integration test at {time.time()}",
            "priority": "high",
            "metadata": {
                "source": "integration_test",
                "timestamp": time.time()
            }
        }
        
        response = await client.post(
            "http://localhost:8001/memory/remember",
            headers=headers,
            json=memory_data
        )
        
        if response.status_code == 200:
            memory_id = response.json()["id"]
            print(f"   ✅ Memory saved: {memory_id}")
        else:
            print(f"   ❌ Memory save failed: {response.status_code}")
            
        # 2. Test plugin execution
        print("\n2. Testing Plugin Manager...")
        
        # First, check available plugins
        response = await client.get(
            "http://localhost:8003/plugins",
            headers=headers
        )
        
        if response.status_code == 200:
            plugins_dict = response.json()["plugins"]
            print(f"   Found {len(plugins_dict)} plugins")
            
            # Execute echo plugin - check if echo exists in plugins dict
            if "echo" in plugins_dict:
                exec_data = {
                    "plugin": "echo",
                    "event_data": {
                        "event_type": "test",
                        "payload": {"message": "Integration test echo"}
                    }
                }
                
                response = await client.post(
                    "http://localhost:8003/plugins/execute",
                    headers=headers,
                    json=exec_data
                )
                
                if response.status_code == 200:
                    result = response.json()
                    if result["success"]:
                        print(f"   ✅ Plugin execution successful")
                    else:
                        print(f"   ❌ Plugin execution failed: {result.get('error')}")
                else:
                    print(f"   ❌ Plugin API error: {response.status_code}")
        
        # 3. Test goal scheduler
        print("\n3. Testing Goal Scheduler...")
        
        # List goals
        response = await client.get(
            "http://localhost:8005/goals",
            headers=headers
        )
        
        if response.status_code == 200:
            goals = response.json()["goals"]
            print(f"   Found {len(goals)} goals")
            
            # Try to run test_goal if it exists
            test_goal = next((g for g in goals if g["id"] == "test_goal"), None)
            if test_goal:
                response = await client.post(
                    "http://localhost:8005/goals/run",
                    headers=headers,
                    json={"goal_id": "test_goal"}
                )
                
                if response.status_code == 200:
                    instance_id = response.json()["instance_id"]
                    print(f"   ✅ Goal queued: {instance_id}")
                else:
                    print(f"   ❌ Goal run failed: {response.status_code}")
            else:
                print("   ℹ️  test_goal not found (this is OK)")
        
        print("\n✅ Integration test completed!")

if __name__ == "__main__":
    asyncio.run(test_integration())
EOF

python /tmp/integration_test.py

echo ""
echo "4️⃣ Checking Event Bus activity..."
echo ""

# Check Redis streams
docker exec titan-redis-master redis-cli XLEN chat.v1 | xargs -I {} echo "   chat.v1: {} events"
docker exec titan-redis-master redis-cli XLEN system.v1 | xargs -I {} echo "   system.v1: {} events"
docker exec titan-redis-master redis-cli XLEN plugin.v1 | xargs -I {} echo "   plugin.v1: {} events"

echo ""
echo "5️⃣ System health summary..."
echo ""

# Memory stats
echo "Memory Service:"
curl -s -H "Authorization: Bearer ${ADMIN_TOKEN:-titan-secret-token-change-me-in-production}" http://localhost:8001/memory/stats 2>/dev/null | \
    python -c "import sys, json; data=json.load(sys.stdin); print(f'   Total memories: {data.get(\"total_memories\", 0)}')" 2>/dev/null || \
    echo "   Stats endpoint not available"

# Plugin stats
echo ""
echo "Plugin Manager:"
curl -s -H "Authorization: Bearer ${ADMIN_TOKEN:-titan-secret-token-change-me-in-production}" http://localhost:8003/plugins 2>/dev/null | \
    python -c "import sys, json; data=json.load(sys.stdin); print(f'   Active plugins: {len(data.get(\"plugins\", {}))}')" 2>/dev/null || \
    echo "   Cannot get plugin count"

# Goal stats
echo ""
echo "Goal Scheduler:"
curl -s -H "Authorization: Bearer ${ADMIN_TOKEN:-titan-secret-token-change-me-in-production}" http://localhost:8005/goals 2>/dev/null | \
    python -c "import sys, json; data=json.load(sys.stdin); print(f'   Configured goals: {data.get(\"total\", 0)}')" 2>/dev/null || \
    echo "   Cannot get goal count"

echo ""
echo "=============================="
echo -e "${GREEN}✅ TITAN SYSTEM TEST COMPLETE${NC}"
echo "=============================="
echo ""
echo "Next steps:"
echo "  - Check logs: docker compose logs -f"
echo "  - Monitor metrics: http://localhost:9090 (Prometheus)"
echo "  - View graphs: http://localhost:3000 (Grafana)"
echo "  - Manage goals: python titan-goals.py list"
