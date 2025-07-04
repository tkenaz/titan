-- Model Gateway Insights Tables for PgVector
-- Run this in pgAdmin in chatGPT database

-- Enable pgvector extension if not already enabled
CREATE EXTENSION IF NOT EXISTS vector;

-- Main insights table
CREATE TABLE IF NOT EXISTS model_insights (
    id BIGSERIAL PRIMARY KEY,
    trace_id TEXT UNIQUE NOT NULL,
    model TEXT NOT NULL,
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    
    -- Request data
    messages JSONB NOT NULL,
    temperature FLOAT,
    max_tokens INTEGER,
    
    -- Response data
    response_text TEXT,
    prompt_tokens INTEGER NOT NULL,
    completion_tokens INTEGER NOT NULL,
    total_tokens INTEGER NOT NULL,
    
    -- Cost data
    input_cost DECIMAL(10, 6) NOT NULL,
    output_cost DECIMAL(10, 6) NOT NULL,
    total_cost DECIMAL(10, 6) NOT NULL,
    
    -- Performance
    latency_ms FLOAT NOT NULL,
    status TEXT NOT NULL,
    error TEXT,
    
    -- Embeddings for semantic search (384 dimensions for all-MiniLM-L6-v2)
    request_embedding vector(384),
    response_embedding vector(384),
    
    -- Metadata
    metadata JSONB DEFAULT '{}'::jsonb
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_model_insights_model ON model_insights(model);
CREATE INDEX IF NOT EXISTS idx_model_insights_timestamp ON model_insights(timestamp);
CREATE INDEX IF NOT EXISTS idx_model_insights_status ON model_insights(status);
CREATE INDEX IF NOT EXISTS idx_model_insights_trace_id ON model_insights(trace_id);

-- Hourly aggregated stats
CREATE TABLE IF NOT EXISTS model_stats_hourly (
    id BIGSERIAL PRIMARY KEY,
    model TEXT NOT NULL,
    hour TIMESTAMPTZ NOT NULL,
    
    -- Counts
    request_count INTEGER DEFAULT 0,
    success_count INTEGER DEFAULT 0,
    error_count INTEGER DEFAULT 0,
    
    -- Tokens
    total_prompt_tokens BIGINT DEFAULT 0,
    total_completion_tokens BIGINT DEFAULT 0,
    
    -- Costs
    total_cost DECIMAL(10, 6) DEFAULT 0,
    
    -- Performance
    avg_latency_ms FLOAT,
    p95_latency_ms FLOAT,
    p99_latency_ms FLOAT,
    
    -- Unique constraint
    UNIQUE(model, hour)
);

-- Daily cost trends
CREATE TABLE IF NOT EXISTS model_cost_trends (
    id BIGSERIAL PRIMARY KEY,
    date DATE NOT NULL,
    model TEXT NOT NULL,
    
    -- Daily aggregates
    total_requests INTEGER DEFAULT 0,
    total_tokens BIGINT DEFAULT 0,
    total_cost DECIMAL(10, 6) DEFAULT 0,
    
    -- Usage patterns
    peak_hour INTEGER,
    peak_requests INTEGER,
    
    -- Cost efficiency
    avg_cost_per_request DECIMAL(10, 6),
    avg_tokens_per_request FLOAT,
    
    UNIQUE(date, model)
);

-- Optional: Add comments for documentation
COMMENT ON TABLE model_insights IS 'Detailed logs of all model API calls with embeddings for semantic search';
COMMENT ON TABLE model_stats_hourly IS 'Hourly aggregated statistics for monitoring and alerting';
COMMENT ON TABLE model_cost_trends IS 'Daily cost trends and usage patterns for budgeting';

-- Grant permissions if needed (adjust username)
-- GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO your_app_user;
-- GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO your_app_user;
