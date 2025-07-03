#!/usr/bin/env python3
"""Quick test to verify fixes work."""

import os
import sys
from pathlib import Path

# Set environment
os.environ['OTEL_SDK_DISABLED'] = 'true'
os.environ['TOKENIZERS_PARALLELISM'] = 'false'

sys.path.insert(0, str(Path(__file__).parent))


def test_imports():
    """Test all imports work."""
    print("🧪 Testing imports...")
    
    try:
        print("  - asyncpg...", end="")
        import asyncpg
        print(" ✅")
    except ImportError as e:
        print(f" ❌ {e}")
    
    try:
        print("  - docker...", end="")
        import docker
        print(" ✅")
    except ImportError as e:
        print(f" ❌ {e}")
    
    try:
        print("  - httpx...", end="")
        import httpx
        print(" ✅")
    except ImportError as e:
        print(f" ❌ {e}")
    
    try:
        print("  - memory_service...", end="")
        from memory_service.service import MemoryService
        print(" ✅")
    except ImportError as e:
        print(f" ❌ {e}")
    
    try:
        print("  - plugin_manager...", end="")
        from plugin_manager.enhanced_manager import EnhancedPluginManager
        print(" ✅")
    except ImportError as e:
        print(f" ❌ {e}")
    
    print("\n✅ All imports successful!")


def test_config():
    """Test configuration loading."""
    print("\n🔧 Testing configuration...")
    
    from memory_service.config import MemoryConfig
    
    # Check if local config exists
    local_config = Path("config/memory-local.yaml")
    docker_config = Path("config/memory.yaml")
    
    print(f"  - Local config exists: {local_config.exists()}")
    print(f"  - Docker config exists: {docker_config.exists()}")
    
    if local_config.exists():
        try:
            config = MemoryConfig.from_yaml(str(local_config))
            print(f"  - Loaded local config: ✅")
            print(f"    PostgreSQL: {config.vector_db.dsn}")
            print(f"    Neo4j: {config.graph_db.uri}")
        except Exception as e:
            print(f"  - Failed to load config: ❌ {e}")


def test_env():
    """Test environment variables."""
    print("\n🌍 Testing environment...")
    
    token = os.getenv("ADMIN_TOKEN")
    print(f"  - ADMIN_TOKEN: {'✅ Set' if token else '❌ Not set'}")
    
    redis_url = os.getenv("REDIS_URL")
    print(f"  - REDIS_URL: {redis_url or 'Using default'}")
    
    print(f"  - Running in Docker: {'Yes' if os.path.exists('/.dockerenv') else 'No'}")


if __name__ == "__main__":
    print("TITAN FIXES VERIFICATION")
    print("=" * 50)
    
    test_imports()
    test_config()
    test_env()
    
    print("\n📝 Next steps:")
    print("1. Install missing deps: chmod +x install_missing_deps.sh && ./install_missing_deps.sh")
    print("2. Start databases: ./start_databases.sh")
    print("3. Run Memory API: python -m memory_service.api")
    print("4. Run Plugin API: python -m plugin_manager.api")
    print("5. Test circuit breaker: python test_circuit_breaker.py")
