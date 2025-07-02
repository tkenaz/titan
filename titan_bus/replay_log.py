"""Persistent replay log for Titan Event Bus."""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import AsyncGenerator, Dict, List, Optional
import gzip
from pathlib import Path

import redis.asyncio as redis
from pydantic import BaseModel, Field

from titan_bus.event import Event
from titan_bus.config import EventBusConfig


logger = logging.getLogger(__name__)


class SnapshotMetadata(BaseModel):
    """Metadata for event snapshots."""
    snapshot_id: str
    topic: str
    start_time: datetime
    end_time: datetime
    event_count: int
    compressed_size: int
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ReplayLog:
    """Handles persistent storage and replay of events."""
    
    def __init__(self, config: EventBusConfig, redis_client: redis.Redis):
        self.config = config
        self.redis = redis_client
        self.storage_path = Path("/app/snapshots")  # In production, use S3
        self.storage_path.mkdir(exist_ok=True)
    
    async def create_snapshot(
        self, 
        topic: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> SnapshotMetadata:
        """Create a snapshot of events from a topic."""
        logger.info(f"Creating snapshot for topic {topic}")
        
        # Default time range: last 24 hours
        if not end_time:
            end_time = datetime.utcnow()
        if not start_time:
            start_time = end_time - timedelta(days=1)
        
        # Convert to Redis stream IDs
        start_id = f"{int(start_time.timestamp() * 1000)}-0"
        end_id = f"{int(end_time.timestamp() * 1000)}-0"
        
        # Read events from stream
        events = []
        cursor = start_id
        
        while True:
            batch = await self.redis.xrange(
                topic,
                min=cursor,
                max=end_id,
                count=1000
            )
            
            if not batch:
                break
            
            for msg_id, data in batch:
                try:
                    event = Event.from_redis(data)
                    events.append({
                        "msg_id": msg_id.decode(),
                        "event": event.model_dump()
                    })
                except Exception as e:
                    logger.error(f"Failed to parse event {msg_id}: {e}")
            
            # Update cursor for next batch
            cursor = f"({batch[-1][0].decode()}"
        
        # Create snapshot file
        snapshot_id = f"{topic}_{start_time.strftime('%Y%m%d_%H%M%S')}_{end_time.strftime('%Y%m%d_%H%M%S')}"
        snapshot_path = self.storage_path / f"{snapshot_id}.json.gz"
        
        # Compress and save
        snapshot_data = {
            "metadata": {
                "topic": topic,
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "event_count": len(events),
                "created_at": datetime.utcnow().isoformat()
            },
            "events": events
        }
        
        with gzip.open(snapshot_path, 'wt', encoding='utf-8') as f:
            json.dump(snapshot_data, f)
        
        metadata = SnapshotMetadata(
            snapshot_id=snapshot_id,
            topic=topic,
            start_time=start_time,
            end_time=end_time,
            event_count=len(events),
            compressed_size=snapshot_path.stat().st_size
        )
        
        logger.info(f"Created snapshot {snapshot_id} with {len(events)} events")
        return metadata
    
    async def replay_from_snapshot(
        self,
        snapshot_id: str,
        target_topic: Optional[str] = None,
        speed: float = 1.0
    ) -> AsyncGenerator[Event, None]:
        """Replay events from a snapshot."""
        snapshot_path = self.storage_path / f"{snapshot_id}.json.gz"
        
        if not snapshot_path.exists():
            raise FileNotFoundError(f"Snapshot {snapshot_id} not found")
        
        # Load snapshot
        with gzip.open(snapshot_path, 'rt', encoding='utf-8') as f:
            snapshot_data = json.load(f)
        
        metadata = snapshot_data["metadata"]
        events = snapshot_data["events"]
        
        logger.info(f"Replaying {len(events)} events from snapshot {snapshot_id}")
        
        # Replay events
        last_timestamp = None
        
        for event_data in events:
            event = Event.model_validate(event_data["event"])
            
            # If target topic specified, override
            if target_topic:
                event.topic = target_topic
            
            # Simulate original timing if speed < infinity
            if speed > 0 and speed < float('inf'):
                if last_timestamp:
                    delay = (event.timestamp - last_timestamp).total_seconds() / speed
                    if delay > 0:
                        await asyncio.sleep(delay)
                last_timestamp = event.timestamp
            
            yield event
    
    async def list_snapshots(
        self,
        topic: Optional[str] = None
    ) -> List[SnapshotMetadata]:
        """List available snapshots."""
        snapshots = []
        
        for snapshot_file in self.storage_path.glob("*.json.gz"):
            try:
                with gzip.open(snapshot_file, 'rt', encoding='utf-8') as f:
                    data = json.load(f)
                    metadata = data["metadata"]
                
                snapshot_meta = SnapshotMetadata(
                    snapshot_id=snapshot_file.stem.replace('.json', ''),
                    topic=metadata["topic"],
                    start_time=datetime.fromisoformat(metadata["start_time"]),
                    end_time=datetime.fromisoformat(metadata["end_time"]),
                    event_count=metadata["event_count"],
                    compressed_size=snapshot_file.stat().st_size,
                    created_at=datetime.fromisoformat(metadata["created_at"])
                )
                
                if not topic or snapshot_meta.topic == topic:
                    snapshots.append(snapshot_meta)
                    
            except Exception as e:
                logger.error(f"Failed to read snapshot {snapshot_file}: {e}")
        
        return sorted(snapshots, key=lambda x: x.created_at, reverse=True)
    
    async def cleanup_old_snapshots(self, days: int = 7):
        """Remove snapshots older than specified days."""
        cutoff = datetime.utcnow() - timedelta(days=days)
        removed = 0
        
        for snapshot in await self.list_snapshots():
            if snapshot.created_at < cutoff:
                snapshot_path = self.storage_path / f"{snapshot.snapshot_id}.json.gz"
                try:
                    snapshot_path.unlink()
                    removed += 1
                    logger.info(f"Removed old snapshot {snapshot.snapshot_id}")
                except Exception as e:
                    logger.error(f"Failed to remove snapshot {snapshot.snapshot_id}: {e}")
        
        return removed


# S3 implementation placeholder
class S3ReplayLog(ReplayLog):
    """S3-backed replay log for production use."""
    
    def __init__(self, config: EventBusConfig, redis_client: redis.Redis, s3_config: Dict):
        super().__init__(config, redis_client)
        # Initialize S3 client here
        # self.s3 = boto3.client('s3', **s3_config)
        # self.bucket = s3_config['bucket']
        logger.warning("S3ReplayLog not implemented yet, using local storage")
