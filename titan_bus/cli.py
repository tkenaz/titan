"""CLI commands for Titan Event Bus."""

import asyncio
import click
from datetime import datetime, timedelta

from titan_bus.client import EventBusClient
from titan_bus.config import EventBusConfig
from titan_bus.replay_log import ReplayLog


@click.group()
def cli():
    """Titan Event Bus CLI."""
    pass


@cli.command()
@click.option('--topic', required=True, help='Topic to snapshot')
@click.option('--hours', default=24, help='Hours of history to snapshot')
@click.option('--config', default='/app/config/eventbus.yaml', help='Config file path')
async def snapshot(topic: str, hours: int, config: str):
    """Create a snapshot of events."""
    # Load config
    cfg = EventBusConfig.from_yaml(config)
    
    # Create client
    async with EventBusClient(cfg) as client:
        replay_log = ReplayLog(cfg, client._redis)
        
        # Create snapshot
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=hours)
        
        metadata = await replay_log.create_snapshot(topic, start_time, end_time)
        
        click.echo(f"Created snapshot: {metadata.snapshot_id}")
        click.echo(f"Events: {metadata.event_count}")
        click.echo(f"Size: {metadata.compressed_size} bytes")


@cli.command()
@click.option('--snapshot-id', required=True, help='Snapshot ID to replay')
@click.option('--target-topic', help='Override target topic')
@click.option('--speed', default=1.0, help='Replay speed multiplier')
@click.option('--config', default='/app/config/eventbus.yaml', help='Config file path')
async def replay(snapshot_id: str, target_topic: str, speed: float, config: str):
    """Replay events from snapshot."""
    # Load config
    cfg = EventBusConfig.from_yaml(config)
    
    # Create client
    async with EventBusClient(cfg) as client:
        replay_log = ReplayLog(cfg, client._redis)
        
        # Replay events
        count = 0
        async for event in replay_log.replay_from_snapshot(snapshot_id, target_topic, speed):
            # Publish to bus
            await client.publish(
                topic=event.topic,
                event_type=event.event_type,
                payload=event.payload,
                priority=event.meta.priority
            )
            count += 1
            
            if count % 100 == 0:
                click.echo(f"Replayed {count} events...")
        
        click.echo(f"Replay complete: {count} events")


@cli.command()
@click.option('--topic', help='Filter by topic')
@click.option('--config', default='/app/config/eventbus.yaml', help='Config file path')
async def list_snapshots(topic: str, config: str):
    """List available snapshots."""
    # Load config
    cfg = EventBusConfig.from_yaml(config)
    
    # Create client
    async with EventBusClient(cfg) as client:
        replay_log = ReplayLog(cfg, client._redis)
        
        # List snapshots
        snapshots = await replay_log.list_snapshots(topic)
        
        if not snapshots:
            click.echo("No snapshots found")
            return
        
        click.echo(f"Found {len(snapshots)} snapshots:")
        for snap in snapshots:
            click.echo(f"\n{snap.snapshot_id}")
            click.echo(f"  Topic: {snap.topic}")
            click.echo(f"  Events: {snap.event_count}")
            click.echo(f"  Size: {snap.compressed_size} bytes")
            click.echo(f"  Created: {snap.created_at}")


@cli.command()
@click.option('--days', default=7, help='Remove snapshots older than N days')
@click.option('--config', default='/app/config/eventbus.yaml', help='Config file path')
async def cleanup(days: int, config: str):
    """Clean up old snapshots."""
    # Load config
    cfg = EventBusConfig.from_yaml(config)
    
    # Create client
    async with EventBusClient(cfg) as client:
        replay_log = ReplayLog(cfg, client._redis)
        
        # Cleanup
        removed = await replay_log.cleanup_old_snapshots(days)
        click.echo(f"Removed {removed} old snapshots")


def main():
    """Run async CLI commands."""
    @cli.resultcallback()
    def process_result(result, **kwargs):
        if asyncio.iscoroutine(result):
            asyncio.run(result)
    
    cli()


if __name__ == '__main__':
    main()
