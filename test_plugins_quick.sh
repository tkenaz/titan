#!/bin/bash
# Quick test script for Plugin Loader

echo "🔍 Checking prerequisites..."

# Check Docker
if command -v docker &> /dev/null; then
    echo "✅ Docker installed: $(docker --version)"
else
    echo "❌ Docker not found. Please install Docker."
    exit 1
fi

# Check Redis
if docker ps | grep -q "titan-redis"; then
    echo "✅ Redis is running"
else
    echo "⚠️  Redis not running. Starting..."
    make up
fi

# Check Python packages
echo ""
echo "📦 Installing requirements..."
pip install -r requirements.txt
pip install -r plugin_manager/requirements.txt

echo ""
echo "🧪 Running local test..."
python test_plugin_manager.py
