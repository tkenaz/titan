"""
Model Insights storage using PgVector
Stores model performance, usage patterns, and cost analytics
"""
import os
import json
import asyncio
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
import asyncpg
import numpy as np
from pgvector.asyncpg import register_vector
import logging

logger = logging.getLogger(__name__)


class ModelInsights:
    """Store and analyze model usage insights"""
    
    def __init__(self, db_url: str):
        self.db_url = db_url
        self.pool: Optional[asyncpg.Pool] = None
    
    async def initialize(self):
        """Initialize database connection and tables"""
        self.pool = await asyncpg.create_pool(
            self.db_url,
            min_size=2,
            max_size=10
        )
        
        async with self.pool.acquire() as conn:
            # Register pgvector extension
            await register_vector(conn)
            
            # Create insights table
            await conn.execute("""
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
                    
                    -- Embeddings for semantic search
                    request_embedding vector(384),
                    response_embedding vector(384),
                    
                    -- Metadata
                    metadata JSONB DEFAULT '{}'::jsonb,
                    
                    -- Indexes
                    INDEX idx_model (model),
                    INDEX idx_timestamp (timestamp),
                    INDEX idx_status (status),
                    INDEX idx_trace_id (trace_id)
                );
            """)
            
            # Create aggregated stats table
            await conn.execute("""
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
            """)
            
            # Create cost trends table
            await conn.execute("""
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
            """)
            
            logger.info("Model insights tables initialized")
    
    async def record_insight(
        self,
        trace_id: str,
        model: str,
        messages: List[Dict[str, str]],
        response_text: str,
        usage: Dict[str, int],
        cost: Dict[str, float],
        latency_ms: float,
        status: str = "success",
        error: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Record a model interaction insight"""
        async with self.pool.acquire() as conn:
            # Convert messages to JSONB
            messages_json = json.dumps(messages)
            
            # Insert insight
            await conn.execute("""
                INSERT INTO model_insights (
                    trace_id, model, messages, response_text,
                    temperature, max_tokens,
                    prompt_tokens, completion_tokens, total_tokens,
                    input_cost, output_cost, total_cost,
                    latency_ms, status, error, metadata
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16)
                ON CONFLICT (trace_id) DO NOTHING
            """,
                trace_id, model, messages_json, response_text,
                temperature, max_tokens,
                usage["prompt_tokens"], usage["completion_tokens"], usage["total_tokens"],
                cost["input_cost"], cost["output_cost"], cost["total_cost"],
                latency_ms, status, error,
                json.dumps(metadata or {})
            )
            
            # Update hourly stats
            hour = datetime.utcnow().replace(minute=0, second=0, microsecond=0)
            await self._update_hourly_stats(
                conn, model, hour, usage, cost, latency_ms, status
            )
    
    async def _update_hourly_stats(
        self,
        conn: asyncpg.Connection,
        model: str,
        hour: datetime,
        usage: Dict[str, int],
        cost: Dict[str, float],
        latency_ms: float,
        status: str
    ):
        """Update hourly statistics"""
        is_success = 1 if status == "success" else 0
        is_error = 1 if status != "success" else 0
        
        await conn.execute("""
            INSERT INTO model_stats_hourly (
                model, hour, request_count, success_count, error_count,
                total_prompt_tokens, total_completion_tokens,
                total_cost, avg_latency_ms
            ) VALUES ($1, $2, 1, $3, $4, $5, $6, $7, $8)
            ON CONFLICT (model, hour) DO UPDATE SET
                request_count = model_stats_hourly.request_count + 1,
                success_count = model_stats_hourly.success_count + $3,
                error_count = model_stats_hourly.error_count + $4,
                total_prompt_tokens = model_stats_hourly.total_prompt_tokens + $5,
                total_completion_tokens = model_stats_hourly.total_completion_tokens + $6,
                total_cost = model_stats_hourly.total_cost + $7,
                avg_latency_ms = (
                    model_stats_hourly.avg_latency_ms * model_stats_hourly.request_count + $8
                ) / (model_stats_hourly.request_count + 1)
        """,
            model, hour, is_success, is_error,
            usage["prompt_tokens"], usage["completion_tokens"],
            cost["total_cost"], latency_ms
        )
    
    async def get_model_stats(
        self,
        model: Optional[str] = None,
        hours: int = 24
    ) -> Dict[str, Any]:
        """Get model statistics for the last N hours"""
        since = datetime.utcnow() - timedelta(hours=hours)
        
        async with self.pool.acquire() as conn:
            # Base query
            query = """
                SELECT 
                    model,
                    SUM(request_count) as total_requests,
                    SUM(success_count) as total_success,
                    SUM(error_count) as total_errors,
                    SUM(total_prompt_tokens) as total_prompt_tokens,
                    SUM(total_completion_tokens) as total_completion_tokens,
                    SUM(total_cost) as total_cost,
                    AVG(avg_latency_ms) as avg_latency_ms
                FROM model_stats_hourly
                WHERE hour >= $1
            """
            
            params = [since]
            if model:
                query += " AND model = $2"
                params.append(model)
            
            query += " GROUP BY model"
            
            rows = await conn.fetch(query, *params)
            
            stats = {}
            for row in rows:
                stats[row["model"]] = {
                    "total_requests": row["total_requests"],
                    "success_rate": (
                        row["total_success"] / row["total_requests"] * 100
                        if row["total_requests"] > 0 else 0
                    ),
                    "total_tokens": row["total_prompt_tokens"] + row["total_completion_tokens"],
                    "total_cost": float(row["total_cost"]),
                    "avg_latency_ms": row["avg_latency_ms"],
                    "tokens_per_request": (
                        (row["total_prompt_tokens"] + row["total_completion_tokens"]) / 
                        row["total_requests"]
                        if row["total_requests"] > 0 else 0
                    )
                }
            
            return stats
    
    async def get_cost_trends(
        self,
        days: int = 7,
        model: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get cost trends for the last N days"""
        since = datetime.utcnow().date() - timedelta(days=days)
        
        async with self.pool.acquire() as conn:
            query = """
                SELECT 
                    date,
                    model,
                    total_requests,
                    total_tokens,
                    total_cost,
                    avg_cost_per_request,
                    avg_tokens_per_request
                FROM model_cost_trends
                WHERE date >= $1
            """
            
            params = [since]
            if model:
                query += " AND model = $2"
                params.append(model)
            
            query += " ORDER BY date DESC, model"
            
            rows = await conn.fetch(query, *params)
            
            return [
                {
                    "date": row["date"].isoformat(),
                    "model": row["model"],
                    "requests": row["total_requests"],
                    "tokens": row["total_tokens"],
                    "cost": float(row["total_cost"]),
                    "avg_cost_per_request": float(row["avg_cost_per_request"]),
                    "avg_tokens_per_request": row["avg_tokens_per_request"]
                }
                for row in rows
            ]
    
    async def find_similar_requests(
        self,
        query: str,
        model: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Find similar previous requests using vector similarity"""
        # This would require implementing embedding generation
        # For now, return text search results
        async with self.pool.acquire() as conn:
            query_sql = """
                SELECT 
                    trace_id,
                    model,
                    messages,
                    response_text,
                    total_cost,
                    latency_ms,
                    timestamp
                FROM model_insights
                WHERE response_text ILIKE $1
            """
            
            params = [f"%{query}%"]
            if model:
                query_sql += " AND model = $2"
                params.append(model)
            
            query_sql += " ORDER BY timestamp DESC LIMIT $" + str(len(params) + 1)
            params.append(limit)
            
            rows = await conn.fetch(query_sql, *params)
            
            return [
                {
                    "trace_id": row["trace_id"],
                    "model": row["model"],
                    "messages": json.loads(row["messages"]),
                    "response": row["response_text"][:200] + "..." if len(row["response_text"]) > 200 else row["response_text"],
                    "cost": float(row["total_cost"]),
                    "latency_ms": row["latency_ms"],
                    "timestamp": row["timestamp"].isoformat()
                }
                for row in rows
            ]
    
    async def run_daily_aggregation(self):
        """Run daily aggregation job"""
        yesterday = datetime.utcnow().date() - timedelta(days=1)
        
        async with self.pool.acquire() as conn:
            # Aggregate yesterday's data
            await conn.execute("""
                INSERT INTO model_cost_trends (
                    date, model, total_requests, total_tokens, total_cost,
                    peak_hour, peak_requests,
                    avg_cost_per_request, avg_tokens_per_request
                )
                SELECT 
                    $1 as date,
                    model,
                    SUM(request_count) as total_requests,
                    SUM(total_prompt_tokens + total_completion_tokens) as total_tokens,
                    SUM(total_cost) as total_cost,
                    
                    -- Peak hour
                    (
                        SELECT EXTRACT(HOUR FROM hour)
                        FROM model_stats_hourly h2
                        WHERE h2.model = h1.model
                        AND DATE(h2.hour) = $1
                        ORDER BY h2.request_count DESC
                        LIMIT 1
                    ) as peak_hour,
                    
                    -- Peak requests
                    (
                        SELECT MAX(request_count)
                        FROM model_stats_hourly h2
                        WHERE h2.model = h1.model
                        AND DATE(h2.hour) = $1
                    ) as peak_requests,
                    
                    -- Averages
                    SUM(total_cost) / NULLIF(SUM(request_count), 0) as avg_cost_per_request,
                    CAST(SUM(total_prompt_tokens + total_completion_tokens) AS FLOAT) / 
                        NULLIF(SUM(request_count), 0) as avg_tokens_per_request
                    
                FROM model_stats_hourly h1
                WHERE DATE(hour) = $1
                GROUP BY model
                ON CONFLICT (date, model) DO UPDATE SET
                    total_requests = EXCLUDED.total_requests,
                    total_tokens = EXCLUDED.total_tokens,
                    total_cost = EXCLUDED.total_cost,
                    peak_hour = EXCLUDED.peak_hour,
                    peak_requests = EXCLUDED.peak_requests,
                    avg_cost_per_request = EXCLUDED.avg_cost_per_request,
                    avg_tokens_per_request = EXCLUDED.avg_tokens_per_request
            """, yesterday)
            
            logger.info(f"Daily aggregation completed for {yesterday}")
    
    async def cleanup_old_data(self, days_to_keep: int = 30):
        """Clean up old detailed data"""
        cutoff = datetime.utcnow() - timedelta(days=days_to_keep)
        
        async with self.pool.acquire() as conn:
            # Delete old insights (keep aggregated data)
            deleted = await conn.execute("""
                DELETE FROM model_insights
                WHERE timestamp < $1
            """, cutoff)
            
            logger.info(f"Cleaned up {deleted} old insight records")
    
    async def close(self):
        """Close database connections"""
        if self.pool:
            await self.pool.close()
