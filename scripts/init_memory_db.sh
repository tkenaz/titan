#!/bin/bash
# Initialize databases for Memory Service

echo "Initializing PostgreSQL with pgvector..."

# Install pgvector extension if not exists
PGPASSWORD=Frfgekmrj391 psql -h 127.0.0.1 -U postgres -d chatGPT << EOF
CREATE EXTENSION IF NOT EXISTS vector;
\dx
EOF

echo "PostgreSQL initialized!"

echo "Testing Neo4j connection..."
# Test Neo4j connection
curl -u neo4j:Frfgekmrj391 http://127.0.0.1:7474/db/neo4j/tx -X POST \
  -H "Content-Type: application/json" \
  -d '{"statements":[{"statement":"RETURN 1 as test"}]}'

echo -e "\n\nTesting Redis connection..."
redis-cli ping

echo -e "\n\nAll databases ready for Memory Service!"
