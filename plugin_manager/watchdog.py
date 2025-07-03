"""Container Watchdog - cleans up zombie containers and enforces TTL."""

import asyncio
import logging
import subprocess
from datetime import datetime, timedelta
from typing import List, Dict
import json

logger = logging.getLogger(__name__)


class ContainerWatchdog:
    """Monitor and clean up Docker containers created by plugins."""
    
    def __init__(
        self,
        container_ttl_minutes: int = 10,
        check_interval_seconds: int = 60,
        label_filter: str = "titan.plugin"
    ):
        self.container_ttl = timedelta(minutes=container_ttl_minutes)
        self.check_interval = check_interval_seconds
        self.label_filter = label_filter
        self._running = False
    
    async def start(self):
        """Start the watchdog loop."""
        self._running = True
        logger.info(
            f"Container watchdog started. "
            f"TTL: {self.container_ttl.total_seconds()}s, "
            f"Check interval: {self.check_interval}s"
        )
        
        # Initial cleanup on start
        await self.cleanup_exited_containers()
        
        # Start monitoring loop
        asyncio.create_task(self._monitor_loop())
    
    async def stop(self):
        """Stop the watchdog."""
        self._running = False
        logger.info("Container watchdog stopped")
    
    async def _monitor_loop(self):
        """Main monitoring loop."""
        while self._running:
            try:
                await self.cleanup_expired_containers()
                await self.cleanup_exited_containers()
            except Exception as e:
                logger.error(f"Watchdog error: {e}", exc_info=True)
            
            await asyncio.sleep(self.check_interval)
    
    async def cleanup_exited_containers(self) -> int:
        """Remove all exited containers with our label."""
        try:
            # Get exited containers with our label
            cmd = [
                "docker", "ps", "-aq",
                "-f", f"label={self.label_filter}",
                "-f", "status=exited"
            ]
            
            result = await self._run_command(cmd)
            if not result:
                return 0
            
            container_ids = result.strip().split('\n')
            container_ids = [cid for cid in container_ids if cid]
            
            if not container_ids:
                return 0
            
            # Remove them
            logger.info(f"Removing {len(container_ids)} exited containers")
            rm_cmd = ["docker", "rm", "-f"] + container_ids
            await self._run_command(rm_cmd)
            
            return len(container_ids)
            
        except Exception as e:
            logger.error(f"Failed to cleanup exited containers: {e}")
            return 0
    
    async def cleanup_expired_containers(self) -> int:
        """Remove running containers that exceeded TTL."""
        try:
            # Get all containers with our label (including running)
            containers = await self.list_plugin_containers()
            
            now = datetime.utcnow()
            expired_count = 0
            
            for container in containers:
                # Check if container exceeded TTL
                created_at = container.get('created_at')
                if not created_at:
                    continue
                
                age = now - created_at
                if age > self.container_ttl:
                    logger.warning(
                        f"Container {container['id'][:12]} "
                        f"(plugin: {container.get('plugin_name', 'unknown')}) "
                        f"exceeded TTL ({age.total_seconds():.0f}s > {self.container_ttl.total_seconds()}s). "
                        f"Terminating..."
                    )
                    
                    # Kill the container
                    await self._run_command(["docker", "kill", container['id']])
                    await self._run_command(["docker", "rm", "-f", container['id']])
                    expired_count += 1
            
            if expired_count > 0:
                logger.info(f"Terminated {expired_count} expired containers")
            
            return expired_count
            
        except Exception as e:
            logger.error(f"Failed to cleanup expired containers: {e}")
            return 0
    
    async def list_plugin_containers(self) -> List[Dict]:
        """List all containers created by plugins."""
        try:
            # Get container details in JSON format
            cmd = [
                "docker", "ps", "-a",
                "--format", "json",
                "-f", f"label={self.label_filter}"
            ]
            
            result = await self._run_command(cmd)
            if not result:
                return []
            
            containers = []
            for line in result.strip().split('\n'):
                if not line:
                    continue
                
                try:
                    container_json = json.loads(line)
                    
                    # Parse container info
                    container_info = {
                        'id': container_json.get('ID'),
                        'name': container_json.get('Names'),
                        'state': container_json.get('State'),
                        'status': container_json.get('Status'),
                        'created': container_json.get('CreatedAt'),
                        'plugin_name': container_json.get('Labels', {}).get('titan.plugin.name'),
                        'event_id': container_json.get('Labels', {}).get('titan.event.id')
                    }
                    
                    # Parse creation time
                    created_str = container_info['created']
                    if created_str:
                        # Docker format: "2023-07-03 10:00:00 +0000 UTC"
                        try:
                            # Remove timezone part for simple parsing
                            created_str = created_str.split(' +')[0]
                            container_info['created_at'] = datetime.strptime(
                                created_str, "%Y-%m-%d %H:%M:%S"
                            )
                        except:
                            # Fallback to current time if parsing fails
                            container_info['created_at'] = datetime.utcnow()
                    
                    containers.append(container_info)
                    
                except json.JSONDecodeError:
                    logger.warning(f"Failed to parse container JSON: {line}")
                    continue
            
            return containers
            
        except Exception as e:
            logger.error(f"Failed to list containers: {e}")
            return []
    
    async def get_container_stats(self) -> Dict:
        """Get statistics about plugin containers."""
        containers = await self.list_plugin_containers()
        
        stats = {
            'total': len(containers),
            'running': 0,
            'exited': 0,
            'by_plugin': {},
            'oldest_age_seconds': 0
        }
        
        now = datetime.utcnow()
        
        for container in containers:
            # Count by state
            if container['state'] == 'running':
                stats['running'] += 1
            elif container['state'] == 'exited':
                stats['exited'] += 1
            
            # Count by plugin
            plugin_name = container.get('plugin_name', 'unknown')
            stats['by_plugin'][plugin_name] = stats['by_plugin'].get(plugin_name, 0) + 1
            
            # Find oldest
            if container.get('created_at'):
                age = (now - container['created_at']).total_seconds()
                stats['oldest_age_seconds'] = max(stats['oldest_age_seconds'], age)
        
        return stats
    
    async def force_cleanup_all(self):
        """Force cleanup all plugin containers (emergency use)."""
        logger.warning("Force cleanup of ALL plugin containers requested")
        
        try:
            # Get all containers with our label
            cmd = [
                "docker", "ps", "-aq",
                "-f", f"label={self.label_filter}"
            ]
            
            result = await self._run_command(cmd)
            if not result:
                return 0
            
            container_ids = result.strip().split('\n')
            container_ids = [cid for cid in container_ids if cid]
            
            if not container_ids:
                logger.info("No plugin containers to cleanup")
                return 0
            
            # Force remove all
            logger.warning(f"Force removing {len(container_ids)} containers")
            rm_cmd = ["docker", "rm", "-f"] + container_ids
            await self._run_command(rm_cmd)
            
            return len(container_ids)
            
        except Exception as e:
            logger.error(f"Failed to force cleanup: {e}")
            return 0
    
    async def _run_command(self, cmd: List[str]) -> str:
        """Run a shell command asynchronously."""
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await proc.communicate()
            
            if proc.returncode != 0:
                error_msg = stderr.decode().strip()
                if error_msg and "No such container" not in error_msg:
                    logger.warning(f"Command failed: {' '.join(cmd)}: {error_msg}")
                return ""
            
            return stdout.decode().strip()
            
        except Exception as e:
            logger.error(f"Failed to run command {' '.join(cmd)}: {e}")
            return ""


# Utility function for manual cleanup
async def emergency_cleanup():
    """Emergency cleanup function."""
    watchdog = ContainerWatchdog()
    
    print("🚨 Emergency container cleanup")
    print("=" * 50)
    
    # Get current stats
    stats = await watchdog.get_container_stats()
    print(f"\nCurrent state:")
    print(f"  Total containers: {stats['total']}")
    print(f"  Running: {stats['running']}")
    print(f"  Exited: {stats['exited']}")
    print(f"\nBy plugin:")
    for plugin, count in stats['by_plugin'].items():
        print(f"  {plugin}: {count}")
    
    # Perform cleanup
    print("\nCleaning up...")
    removed = await watchdog.force_cleanup_all()
    print(f"✅ Removed {removed} containers")


if __name__ == "__main__":
    # Run emergency cleanup if called directly
    asyncio.run(emergency_cleanup())
