#!/bin/bash
# Stop all Titan services

echo "🛑 Stopping Titan Services..."

# Function to stop service
stop_service() {
    local name=$1
    local pid_file="logs/${name}.pid"
    
    if [ -f "$pid_file" ]; then
        pid=$(cat "$pid_file")
        if kill -0 $pid 2>/dev/null; then
            echo "Stopping $name (PID: $pid)..."
            kill $pid
            rm -f "$pid_file"
            echo "✅ $name stopped"
        else
            echo "⚠️  $name not running (stale PID file)"
            rm -f "$pid_file"
        fi
    else
        echo "⚠️  $name not found"
    fi
}

# Stop all services
stop_service "memory-api"
stop_service "plugin-api"
stop_service "memory-consumer"

echo ""
echo "✅ All services stopped"
echo ""
echo "To stop databases: docker-compose -f docker-compose.databases.yml down"
