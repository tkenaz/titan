#!/bin/bash
# Start all databases for local testing

echo "🚀 Starting databases for Titan..."

# Stop any existing containers
docker-compose -f docker-compose.databases.yml down

# Start databases
docker-compose -f docker-compose.databases.yml up -d

# Wait for services to be healthy
echo "⏳ Waiting for databases to be ready..."
sleep 5

# Check status
echo "📊 Checking database status..."
docker-compose -f docker-compose.databases.yml ps

# Show connection info
echo ""
echo "✅ Databases are ready!"
echo "📌 Connection info:"
echo "   PostgreSQL: postgresql://postgres:Frfgekmrj391@localhost:5432/chatGPT"
echo "   Neo4j:      bolt://neo4j:Frfgekmrj391@localhost:7687"
echo "   Redis:      redis://localhost:6379"
echo ""
echo "🌐 Neo4j Browser: http://localhost:7474 (user: neo4j, pass: Frfgekmrj391)"
