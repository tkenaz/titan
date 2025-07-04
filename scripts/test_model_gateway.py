#!/usr/bin/env python3
"""
Interactive Model Gateway Test
"""
import os
import asyncio
import httpx
import json
from typing import Dict, Any
from datetime import datetime

# Configuration
BASE_URL = "http://localhost:8081"
TOKEN = os.getenv("ADMIN_TOKEN", "titan-secret-token-change-me-in-production")
HEADERS = {"Authorization": f"Bearer {TOKEN}"}


async def test_health():
    """Test health endpoint"""
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/health")
        print(f"✓ Health: {response.json()}")


async def test_models():
    """List available models"""
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/models")
        data = response.json()
        
        print("\n📊 Available Models:")
        for model in data["models"]:
            print(f"  - {model['name']}:")
            print(f"    Input: ${model['input_cost']}/token")
            print(f"    Output: ${model['output_cost']}/token")
            print(f"    Max tokens: {model['max_tokens']}")
        
        print(f"\n💰 Budget Status:")
        budget = data["budget"]
        print(f"  Daily limit: ${budget['daily_limit_usd']}")
        print(f"  Spent: ${budget['daily_spent_usd']:.4f}")
        print(f"  Remaining: ${budget['remaining_usd']:.4f}")


async def test_completion(model: str = "gpt-4o", message: str = "Hello! Reply in 5 words."):
    """Test non-streaming completion"""
    async with httpx.AsyncClient(timeout=30.0) as client:
        print(f"\n🤖 Testing {model}...")
        start = datetime.now()
        
        response = await client.post(
            f"{BASE_URL}/proxy/{model}",
            headers=HEADERS,
            json={
                "messages": [{"role": "user", "content": message}],
                "temperature": 0.7,
                "stream": False
            }
        )
        
        if response.status_code == 200:
            data = response.json()
            elapsed = (datetime.now() - start).total_seconds()
            
            print(f"✓ Response: {data['choices'][0]['message']['content']}")
            print(f"  Tokens: {data['usage']['total_tokens']}")
            print(f"  Cost: ${data['cost']['total_cost']:.6f}")
            print(f"  Time: {elapsed:.2f}s")
            print(f"  Trace: {data['id']}")
            
            if 'signature' in data:
                print(f"  Signature: {data['signature'][:32]}...")
        else:
            print(f"✗ Error {response.status_code}: {response.text}")


async def test_streaming(model: str = "gpt-4o"):
    """Test streaming completion"""
    async with httpx.AsyncClient(timeout=30.0) as client:
        print(f"\n🌊 Testing streaming {model}...")
        
        response = await client.post(
            f"{BASE_URL}/proxy/{model}",
            headers=HEADERS,
            json={
                "messages": [{"role": "user", "content": "Count from 1 to 5 slowly"}],
                "temperature": 0.7,
                "stream": True
            }
        )
        
        if response.status_code == 200:
            chunks = 0
            full_response = ""
            
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    chunks += 1
                    data_str = line[6:]
                    
                    if data_str == "[DONE]":
                        break
                    
                    try:
                        data = json.loads(data_str)
                        if "error" in data:
                            print(f"✗ Error: {data['error']}")
                            break
                        elif data.get("done"):
                            print(f"\n✓ Streaming complete!")
                            print(f"  Chunks: {chunks}")
                            print(f"  Usage: {data['usage']}")
                            print(f"  Cost: ${data['cost']['total_cost']:.6f}")
                        else:
                            content = data.get("choices", [{}])[0].get("delta", {}).get("content", "")
                            print(content, end="", flush=True)
                            full_response += content
                    except json.JSONDecodeError:
                        pass
            
            print(f"\n  Full response: {full_response}")
        else:
            print(f"✗ Error {response.status_code}: {response.text}")


async def test_budget_enforcement():
    """Test budget limits"""
    print("\n💸 Testing budget enforcement...")
    
    # Make several cheap requests
    for i in range(3):
        await test_completion("gpt-4o", f"Say {i+1}")
    
    # Check budget
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/budget/stats", headers=HEADERS)
        stats = response.json()
        
        print(f"\n📊 Budget after {i+1} requests:")
        print(f"  Spent: ${stats['daily_spent_usd']:.4f}")
        print(f"  Remaining: ${stats['remaining_usd']:.4f}")


async def test_insights():
    """Test insights endpoints"""
    async with httpx.AsyncClient() as client:
        print("\n📈 Testing insights...")
        
        # Stats
        response = await client.get(
            f"{BASE_URL}/insights/stats?hours=1",
            headers=HEADERS
        )
        
        if response.status_code == 200:
            stats = response.json()
            print("✓ Model stats:", json.dumps(stats, indent=2))
        elif response.status_code == 503:
            print("ℹ️  Insights not configured (PostgreSQL not connected)")
        else:
            print(f"✗ Error: {response.status_code}")


async def main():
    """Run all tests"""
    print("🚀 Model Gateway Test Suite\n")
    
    try:
        await test_health()
        await test_models()
        await test_completion()
        await test_streaming()
        # await test_budget_enforcement()  # Commented to save money
        await test_insights()
        
        print("\n✅ All tests completed!")
        
    except httpx.ConnectError:
        print("❌ Cannot connect to Model Gateway. Is it running?")
        print("   Run: make gateway-up")
    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    asyncio.run(main())
