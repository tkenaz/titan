FROM python:3.12-slim

WORKDIR /app

# Install system dependencies (Docker CLI)
RUN apt-get update && apt-get install -y \
    docker.io \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY plugin_manager/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy and install titan_bus
COPY titan_bus /app/titan_bus
COPY setup.py /app/titan_bus/
RUN cd /app/titan_bus && pip install -e .

# Copy plugin manager
COPY plugin_manager /app/plugin_manager
COPY plugins /app/plugins
COPY config/plugins.yaml /app/config/

# Create logs directory
RUN mkdir -p /app/logs/plugins

# Expose ports
EXPOSE 8003 8004

# Run service
CMD ["python", "-m", "uvicorn", "plugin_manager.api:app", "--host", "0.0.0.0", "--port", "8003"]
