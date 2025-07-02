"""Setup for Plugin Manager."""

from setuptools import setup, find_packages

setup(
    name="titan-plugin-manager",
    version="0.1.0",
    description="Dynamic plugin management for Titan",
    author="Titan Team",
    packages=find_packages(),
    python_requires=">=3.10",
    install_requires=[
        "fastapi>=0.104.0",
        "uvicorn[standard]>=0.24.0",
        "pydantic>=2.5.0",
        "pydantic-settings>=2.1.0",
        "PyYAML>=6.0",
        "asyncio>=3.4.3",
        "aiofiles>=23.0.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.4.0",
            "pytest-asyncio>=0.23.0",
            "httpx>=0.25.0",
        ]
    },
    entry_points={
        "console_scripts": [
            "titan-plugins=titan-plugins:cli",
        ],
    },
)
