#!/bin/bash
# Test memory search directly in PostgreSQL

echo "Testing direct PostgreSQL search..."

PGPASSWORD=Frfgekmrj391 psql -h 127.0.0.1 -U postgres -d chatGPT << EOF
-- Show all memories
SELECT id, summary, static_priority, tags, embedding IS NULL as no_embedding 
FROM memory_entries;

-- Text search
SELECT id, summary 
FROM memory_entries 
WHERE summary ILIKE '%рост%';

-- Check if embeddings are stored
SELECT id, length(embedding::text) as embedding_length 
FROM memory_entries 
WHERE embedding IS NOT NULL;
EOF
