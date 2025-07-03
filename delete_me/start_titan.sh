#!/bin/bash
# Start all Titan services

echo "🚀 Starting Titan Services..."
echo "================================"

# Check environment
if [ -z "$ADMIN_TOKEN" ]; then
    export ADMIN_TOKEN="titan-secret-token-change-me-in-production"
    echo "⚠️  Using default ADMIN_TOKEN (change in production!)"
fi

# Install dependencies if needed
if ! python -c "import docker" 2>/dev/null; then
    echo "📦 Installing missing dependencies..."
    pip install docker asyncpg httpx watchdog
fi

# Start databases if not running
if ! nc -z localhost 5432 2>/dev/null; then
    echo "🗄️  Starting databases..."
    ./start_databases.sh
    sleep 10
fi

# Function to run service in background
run_service() {
    local name=$1
    local module=$2
    local log_file="logs/${name}.log"
    
    mkdir -p logs
    
    echo "Starting $name..."
    python -m $module > $log_file 2>&1 &
    echo "$!" > "logs/${name}.pid"
    
    # Wait a bit and check if started
    sleep 2
    if kill -0 $(cat "logs/${name}.pid") 2>/dev/null; then
        echo "✅ $name started (PID: $(cat logs/${name}.pid))"
    else
        echo "❌ $name failed to start. Check $log_file"
        tail -n 10 $log_file
    fi
}

# Start services
echo ""
echo "🧠 Starting Memory Service..."
run_service "memory-api" "memory_service.api"

echo ""
echo "🔌 Starting Plugin Manager..."
run_service "plugin-api" "plugin_manager.api"

echo ""
echo "📡 Starting Memory Consumer..."
run_service "memory-consumer" "memory_service.consumer"

echo ""
echo "✅ All services started!"
echo ""
echo "📊 Service URLs:"
echo "  - Memory API: http://localhost:8001"
echo "  - Plugin API: http://localhost:8003"
echo "  - Memory Metrics: http://localhost:8001/metrics"
echo "  - Plugin Metrics: http://localhost:8003/metrics"
echo ""
echo "🔑 Auth header: Authorization: Bearer $ADMIN_TOKEN"
echo ""
echo "📝 To stop all services: ./stop_titan.sh"
