"""
WebSocket Bridge for Titan Event Bus
Bridges Redis Streams to WebSocket clients
"""
import asyncio
import json
import logging
from typing import Set
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import redis.asyncio as redis
import uvicorn

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Titan WebSocket Bridge")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Connected clients
clients: Set[WebSocket] = set()

# Redis connection
redis_client = None

async def get_redis():
    global redis_client
    if not redis_client:
        redis_client = await redis.from_url("redis://localhost:6379", decode_responses=True)
    return redis_client

@app.on_event("startup")
async def startup():
    await get_redis()
    # Start consuming events
    asyncio.create_task(consume_events())

@app.on_event("shutdown")
async def shutdown():
    if redis_client:
        await redis_client.close()

@app.get("/health")
async def health():
    return {"status": "healthy", "clients": len(clients)}

@app.websocket("/events")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    clients.add(websocket)
    logger.info(f"Client connected. Total clients: {len(clients)}")
    
    try:
        while True:
            # Keep connection alive
            await websocket.receive_text()
    except WebSocketDisconnect:
        clients.remove(websocket)
        logger.info(f"Client disconnected. Total clients: {len(clients)}")

async def consume_events():
    """Consume events from Redis and broadcast to WebSocket clients"""
    redis = await get_redis()
    last_id = "$"
    
    while True:
        try:
            # Read from multiple streams
            streams = await redis.xread({
                "agent.events": last_id,
                "system.v1": "$",
                "goals.events": "$",
                "plugins.events": "$"
            }, block=1000)
            
            for stream_name, messages in streams:
                for message_id, data in messages:
                    # Update last_id for agent.events
                    if stream_name == "agent.events":
                        last_id = message_id
                    
                    # Broadcast to all connected clients
                    event = {
                        "type": data.get("type", stream_name),
                        "timestamp": data.get("timestamp"),
                        **data
                    }
                    
                    disconnected = set()
                    for client in clients:
                        try:
                            await client.send_json(event)
                        except Exception as e:
                            logger.error(f"Error sending to client: {e}")
                            disconnected.add(client)
                    
                    # Remove disconnected clients
                    for client in disconnected:
                        clients.discard(client)
                        
        except Exception as e:
            logger.error(f"Error consuming events: {e}")
            await asyncio.sleep(1)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8088)
