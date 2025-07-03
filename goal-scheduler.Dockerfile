FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Additional dependencies for Goal Scheduler
RUN pip install --no-cache-dir \
    croniter>=1.3.0 \
    jinja2>=3.1.0 \
    fastapi>=0.109.0 \
    uvicorn[standard]>=0.27.0 \
    httpx>=0.25.0

# Copy goal scheduler package
COPY goal_scheduler /app/goal_scheduler

# Copy goals directory
COPY goals /app/goals

# Copy shared packages
COPY titan_bus /app/titan_bus

# Set Python path
ENV PYTHONPATH=/app

# Default environment variables
ENV SCHEDULER_REDIS_URL=redis://redis:6379/2
ENV EVENT_BUS_URL=redis://redis:6379/0
ENV GOALS_DIR=/app/goals

# Run the scheduler
CMD ["python", "-m", "goal_scheduler.api"]
