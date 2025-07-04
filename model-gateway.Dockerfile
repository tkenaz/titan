FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Additional requirements for model gateway
RUN pip install --no-cache-dir \
    openai==1.14.0 \
    tiktoken==0.6.0 \
    httpx==0.27.0 \
    pyyaml==6.0.1 \
    asyncpg==0.29.0 \
    pgvector==0.2.4 \
    prometheus-client==0.19.0 \
    uvicorn==0.27.0 \
    fastapi==0.109.0

# Copy model gateway code
COPY model_gateway /app/model_gateway

# Create directories
RUN mkdir -p /app/config /app/logs

# Expose port
EXPOSE 8081

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8081/health || exit 1

# Run the application
CMD ["python", "-m", "uvicorn", "model_gateway.app:app", "--host", "0.0.0.0", "--port", "8081"]
