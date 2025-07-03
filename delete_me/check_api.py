#!/usr/bin/env python3
"""Check API endpoints and authentication."""

import asyncio
import httpx
import os


async def check_api_endpoints():
    """Check all available endpoints."""
    
    base_url = "http://localhost:8001"
    token = os.getenv("ADMIN_TOKEN", "titan-secret-token-change-me-in-production")
    headers = {"Authorization": f"Bearer {token}"}
    
    endpoints = [
        # No auth required
        ("/", "GET", None),
        ("/health", "GET", None),
        ("/metrics", "GET", None),
        ("/docs", "GET", None),
        ("/openapi.json", "GET", None),
        
        # Auth required
        ("/memory/stats", "GET", headers),
        ("/memory/evaluate", "POST", headers),
        ("/memory/search", "POST", headers),
        ("/memory/remember", "POST", headers),
        ("/memory/gc", "POST", headers),
    ]
    
    print("🔍 Checking Memory Service API endpoints...")
    print(f"   Base URL: {base_url}")
    print(f"   Token: {token[:20]}...")
    print("")
    
    async with httpx.AsyncClient(timeout=5.0) as client:
        for endpoint, method, auth_headers in endpoints:
            try:
                if method == "GET":
                    response = await client.get(f"{base_url}{endpoint}", headers=auth_headers)
                else:
                    # For POST endpoints, just check if they exist
                    response = await client.post(f"{base_url}{endpoint}", headers=auth_headers, json={})
                
                status = response.status_code
                auth_info = "🔐 Auth" if auth_headers else "🔓 No auth"
                
                if status == 200:
                    print(f"✅ {method:4} {endpoint:25} {auth_info} → {status}")
                elif status == 422:  # Unprocessable Entity (missing required fields)
                    print(f"✅ {method:4} {endpoint:25} {auth_info} → {status} (endpoint exists)")
                elif status == 401:
                    print(f"🔒 {method:4} {endpoint:25} {auth_info} → {status} Unauthorized")
                elif status == 404:
                    print(f"❌ {method:4} {endpoint:25} {auth_info} → {status} Not Found")
                else:
                    print(f"⚠️  {method:4} {endpoint:25} {auth_info} → {status}")
                    
            except Exception as e:
                print(f"❌ {method:4} {endpoint:25} → Error: {e}")
    
    print("\n📝 Testing authentication flow...")
    
    # Test auth on a protected endpoint
    test_endpoint = "/memory/stats"
    
    print(f"\nTesting {test_endpoint}:")
    
    async with httpx.AsyncClient() as client:
        # 1. No auth
        print("1. Without auth header:")
        response = await client.get(f"{base_url}{test_endpoint}")
        print(f"   Status: {response.status_code}")
        if response.status_code != 200:
            print(f"   Body: {response.text[:100]}")
        
        # 2. Wrong token
        print("\n2. With wrong token:")
        wrong_headers = {"Authorization": "Bearer wrong-token"}
        response = await client.get(f"{base_url}{test_endpoint}", headers=wrong_headers)
        print(f"   Status: {response.status_code}")
        if response.status_code != 200:
            print(f"   Body: {response.text[:100]}")
        
        # 3. Correct token
        print("\n3. With correct token:")
        response = await client.get(f"{base_url}{test_endpoint}", headers=headers)
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            print(f"   Body: {response.json()}")
        else:
            print(f"   Body: {response.text[:100]}")


if __name__ == "__main__":
    asyncio.run(check_api_endpoints())
