#!/usr/bin/env python3
"""
Simple streaming test
"""
import asyncio
import httpx
import json
import os

BASE_URL = "http://localhost:8081"
TOKEN = os.getenv("ADMIN_TOKEN", "titan-secret-token-change-me-in-production")

async def test_streaming():
    headers = {"Authorization": f"Bearer {TOKEN}"}
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        print("Testing streaming...")
        
        try:
            response = await client.post(
                f"{BASE_URL}/proxy/gpt-4o",
                headers=headers,
                json={
                    "messages": [{"role": "user", "content": "Count from 1 to 3"}],
                    "temperature": 0.7,
                    "stream": True
                }
            )
            
            print(f"Status: {response.status_code}")
            print(f"Headers: {response.headers}")
            
            if response.status_code == 200:
                print("\nStreaming response:")
                async for line in response.aiter_lines():
                    print(f"Line: {line}")
                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str == "[DONE]":
                            print("Stream complete!")
                            break
                        try:
                            data = json.loads(data_str)
                            print(f"Parsed: {data}")
                        except Exception as e:
                            print(f"Parse error: {e}")
            else:
                print(f"Error response: {await response.aread()}")
                
        except Exception as e:
            print(f"Exception: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_streaming())
