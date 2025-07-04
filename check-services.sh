#!/bin/bash

echo "Checking Titan services..."

# Check Memory Service
if curl -s http://localhost:8001/health > /dev/null; then
    echo "✓ Memory Service (8001) - ONLINE"
else
    echo "✗ Memory Service (8001) - OFFLINE"
fi

# Check Plugin Manager
if curl -s http://localhost:8003/health > /dev/null; then
    echo "✓ Plugin Manager (8003) - ONLINE"
else
    echo "✗ Plugin Manager (8003) - OFFLINE"
fi

# Check Goal Scheduler
if curl -s http://localhost:8005/health > /dev/null; then
    echo "✓ Goal Scheduler (8005) - ONLINE"
else
    echo "✗ Goal Scheduler (8005) - OFFLINE"
fi

# Check Model Gateway
if curl -s http://localhost:8081/health > /dev/null; then
    echo "✓ Model Gateway (8081) - ONLINE"
else
    echo "✗ Model Gateway (8081) - OFFLINE"
fi

# Check WebSocket Bridge
if curl -s http://localhost:8088/health > /dev/null; then
    echo "✓ WebSocket Bridge (8088) - ONLINE"
else
    echo "✗ WebSocket Bridge (8088) - OFFLINE"
fi
