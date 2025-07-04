#!/usr/bin/env python3
"""
Quick PostgreSQL connection test
"""
import os
import asyncio
import asyncpg
from dotenv import load_dotenv

load_dotenv()

async def test_connection():
    db_url = os.getenv("DB_URL")
    print(f"DB_URL: {db_url}")
    
    if not db_url:
        print("❌ DB_URL not found in .env")
        return
    
    try:
        # Test connection
        conn = await asyncpg.connect(db_url)
        print("✅ PostgreSQL connection successful!")
        
        # Check if tables exist
        tables = await conn.fetch("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name LIKE 'model_%'
        """)
        
        print(f"\nModel tables found: {len(tables)}")
        for table in tables:
            print(f"  - {table['table_name']}")
        
        await conn.close()
        
    except Exception as e:
        print(f"❌ Connection failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_connection())
