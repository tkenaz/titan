FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY memory_service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy and install titan_bus
COPY titan_bus /app/titan_bus
COPY setup.py /app/titan_bus/
RUN cd /app/titan_bus && pip install -e .

# Copy memory service
COPY memory_service /app/memory_service
COPY config/memory.yaml /app/config/

# Install service
RUN pip install -e .

# Expose ports
EXPOSE 8001 8002

# Run service
CMD ["python", "-m", "uvicorn", "memory_service.api:app", "--host", "0.0.0.0", "--port", "8001"]
