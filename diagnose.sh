#!/bin/bash
# Quick diagnostics for Titan services

echo "🔍 Titan Services Diagnostics"
echo "============================"
echo ""

# Check Docker containers
echo "📦 Docker containers (titan-*):"
docker ps --filter "name=titan" --format "table {{.Names}}\t{{.Status}}" | head -20
echo ""

# Check ports
echo "🔌 Port availability:"
echo "  - 5432 (PostgreSQL): $(nc -zv localhost 5432 2>&1 | grep -q succeeded && echo "✅ Open" || echo "❌ Closed")"
echo "  - 6379 (Redis Main): $(nc -zv localhost 6379 2>&1 | grep -q succeeded && echo "✅ Open" || echo "❌ Closed")"
echo "  - 6380 (Redis Replica): $(nc -zv localhost 6380 2>&1 | grep -q succeeded && echo "✅ Open" || echo "❌ Closed")"
echo "  - 7474 (Neo4j HTTP): $(nc -zv localhost 7474 2>&1 | grep -q succeeded && echo "✅ Open" || echo "❌ Closed")"
echo "  - 7687 (Neo4j Bolt): $(nc -zv localhost 7687 2>&1 | grep -q succeeded && echo "✅ Open" || echo "❌ Closed")"
echo "  - 8001 (Memory API): $(nc -zv localhost 8001 2>&1 | grep -q succeeded && echo "✅ Open" || echo "❌ Closed")"
echo "  - 8003 (Plugin API): $(nc -zv localhost 8003 2>&1 | grep -q succeeded && echo "✅ Open" || echo "❌ Closed")"
echo ""

# Quick API checks
echo "🌐 API Health Checks:"
echo -n "  - Memory Service: "
curl -s http://localhost:8001/health | jq -c '.' 2>/dev/null || echo "Not responding"
echo -n "  - Plugin Manager: "
curl -s http://localhost:8003/health | jq -c '.' 2>/dev/null || echo "Not responding"
echo ""

# Check logs for errors
echo "⚠️  Recent errors (last 10 lines):"
echo "Memory Service:"
docker logs titan-memory-service 2>&1 | grep -i error | tail -5 || echo "  No recent errors"
echo ""
echo "Plugin Manager:"
docker logs titan-plugin-manager 2>&1 | grep -i error | tail -5 || echo "  No recent errors"
echo ""

# Summary
echo "📊 Summary:"
if curl -s http://localhost:8001/health | grep -q healthy && \
   curl -s http://localhost:8003/health | grep -q healthy; then
    echo "✅ Core services are running!"
    echo ""
    echo "You can now run: python test_circuit_breaker.py"
else
    echo "❌ Some services are not healthy"
    echo ""
    echo "Try running: ./start_services.sh"
fi
