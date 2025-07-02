"""Setup configuration for Memory Service."""

from setuptools import setup, find_packages

setup(
    name="memory-service",
    version="0.1.0",
    description="Long-term and short-term memory for Titan",
    author="Titan Team",
    author_email="titan@example.com",
    license="MIT",
    packages=find_packages(include=["memory_service", "memory_service.*"]),
    python_requires=">=3.12",
    install_requires=[
        "fastapi>=0.109.0",
        "uvicorn[standard]>=0.27.0",
        "pydantic>=2.5.0",
        "pydantic-settings>=2.1.0",
        "asyncpg>=0.29.0",
        "pgvector>=0.2.4",
        "neo4j>=5.16.0",
        "redis[hiredis]>=5.0.0",
        "numpy>=1.26.0",
        "ulid-py>=1.1.0",
        "python-multipart>=0.0.6",
        "prometheus-client>=0.19.0",
        "opentelemetry-api>=1.22.0",
        "opentelemetry-sdk>=1.22.0",
        "opentelemetry-instrumentation-fastapi>=0.44b0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.4.0",
            "pytest-asyncio>=0.23.0",
            "pytest-cov>=4.1.0",
            "pytest-mock>=3.12.0",
            "black>=23.12.0",
            "ruff>=0.1.0",
            "mypy>=1.8.0",
        ],
        "embeddings": [
            "openai>=1.0.0",
            "sentence-transformers>=2.2.0",
        ]
    },
)
