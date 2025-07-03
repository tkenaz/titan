#!/usr/bin/env python3
"""Check OpenAPI schema to see registered endpoints."""

import asyncio
import httpx
import json


async def check_openapi():
    """Check OpenAPI schema for available endpoints."""
    
    async with httpx.AsyncClient() as client:
        # Get OpenAPI schema
        response = await client.get("http://localhost:8001/openapi.json")
        
        if response.status_code == 200:
            schema = response.json()
            
            print("🔍 Memory Service API Endpoints (from OpenAPI):")
            print(f"   Title: {schema.get('info', {}).get('title')}")
            print(f"   Version: {schema.get('info', {}).get('version')}")
            print("\nAvailable endpoints:")
            
            paths = schema.get('paths', {})
            for path, methods in sorted(paths.items()):
                for method, details in methods.items():
                    auth = "🔐" if details.get('security') else "🔓"
                    summary = details.get('summary', 'No description')
                    print(f"   {auth} {method.upper():6} {path:30} - {summary}")
            
            # Check if /memory/stats exists
            if '/memory/stats' not in paths:
                print("\n❌ /memory/stats endpoint is NOT registered!")
                print("   This explains the 404 errors.")
            
            # Save schema for inspection
            with open('memory_api_schema.json', 'w') as f:
                json.dump(schema, f, indent=2)
            print("\n📄 Full schema saved to memory_api_schema.json")
            
        else:
            print(f"❌ Failed to get OpenAPI schema: {response.status_code}")


if __name__ == "__main__":
    asyncio.run(check_openapi())
