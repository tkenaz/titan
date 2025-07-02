"""Setup configuration for Titan Bus."""

from setuptools import setup, find_packages

setup(
    name="titan-bus",
    version="0.1.0",
    description="Event-driven core for Titan project",
    author="Titan Team",
    author_email="titan@example.com",
    license="MIT",
    packages=find_packages(include=["titan_bus", "titan_bus.*"]),
    python_requires=">=3.12",
    install_requires=[
        "redis[hiredis]>=5.0.0",
        "aioredis>=2.0.1", 
        "asyncio>=3.4.3",
        "pydantic>=2.5.0",
        "pydantic-settings>=2.1.0",
        "ulid-py>=1.1.0",
        "PyYAML>=6.0",
        "prometheus-client>=0.19.0",
        "opentelemetry-api>=1.22.0",
        "opentelemetry-sdk>=1.22.0",
        "opentelemetry-instrumentation-redis>=0.44b0",
        "opentelemetry-exporter-otlp>=1.22.0",
        "click>=8.1.0",
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
        ]
    },
    entry_points={
        "console_scripts": [
            "titan-bus=titan_bus.cli:main",
        ],
    },
)
