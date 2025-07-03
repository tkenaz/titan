"""File Watcher Plugin - watches directories and notifies about changes."""

import asyncio
import os
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Dict, Any
import mimetypes

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from titan_bus import EventBusClient
from titan_bus.config import EventBusConfig
import logging

logger = logging.getLogger(__name__)


class TitanFileHandler(FileSystemEventHandler):
    """Enhanced file handler that publishes summaries to Event Bus."""
    
    def __init__(self, bus_client: EventBusClient):
        self.bus_client = bus_client
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
    
    def on_created(self, event):
        """Handle file creation."""
        if event.is_directory:
            return
        
        self.loop.run_until_complete(
            self._process_file_event("file_created", event.src_path)
        )
    
    def on_modified(self, event):
        """Handle file modification."""
        if event.is_directory:
            return
        
        self.loop.run_until_complete(
            self._process_file_event("file_modified", event.src_path)
        )
    
    def on_deleted(self, event):
        """Handle file deletion."""
        if event.is_directory:
            return
        
        self.loop.run_until_complete(
            self._process_file_event("file_deleted", event.src_path)
        )
    
    async def _process_file_event(self, event_type: str, path: str):
        """Process file event and publish to Event Bus."""
        file_path = Path(path)
        
        # Basic file info
        payload = {
            "path": str(file_path),
            "name": file_path.name,
            "extension": file_path.suffix,
            "event_source": "file_watcher",
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Add file metadata if file exists
        if file_path.exists() and event_type != "file_deleted":
            try:
                stat = file_path.stat()
                payload.update({
                    "size": stat.st_size,
                    "size_human": self._human_size(stat.st_size),
                    "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    "mime_type": mimetypes.guess_type(str(file_path))[0],
                    "hash": await self._get_file_hash(file_path) if stat.st_size < 10_000_000 else None
                })
                
                # Generate summary for important files
                summary = await self._generate_summary(event_type, file_path, payload)
                if summary:
                    payload["summary"] = summary
                
            except Exception as e:
                logger.error(f"Error processing file {file_path}: {e}")
        
        # Publish to fs.v1 topic
        await self.bus_client.publish(
            topic="fs.v1",
            event_type=event_type,
            payload=payload,
            priority="high" if self._is_important_file(file_path) else "medium"
        )
        
        # For important files, also publish summary to system.v1 for Memory Service
        if self._is_important_file(file_path) and "summary" in payload:
            await self.bus_client.publish(
                topic="system.v1",
                event_type="file_summary",
                payload={
                    "message": payload["summary"],
                    "source": "file_watcher",
                    "context": {
                        "file_path": str(file_path),
                        "file_type": file_path.suffix,
                        "event_type": event_type,
                        "importance": "high"
                    }
                }
            )
        
        logger.info(f"Processed {event_type} for {file_path.name}")
    
    async def _generate_summary(self, event_type: str, file_path: Path, metadata: Dict[str, Any]) -> str:
        """Generate human-readable summary for file event."""
        action_map = {
            "file_created": "создан",
            "file_modified": "изменен",
            "file_deleted": "удален"
        }
        
        action = action_map.get(event_type, event_type)
        file_type = self._get_file_type_description(file_path)
        size = metadata.get("size_human", "unknown size")
        
        summary = f"Файл {file_path.name} ({file_type}, {size}) был {action}"
        
        # Add context for specific file types
        if file_path.suffix in ['.md', '.txt']:
            summary += ". Это может быть важная документация или заметки"
        elif file_path.suffix in ['.py', '.js', '.ts']:
            summary += ". Изменения в коде могут требовать внимания"
        elif file_path.suffix in ['.yaml', '.yml', '.json']:
            summary += ". Конфигурационный файл может влиять на работу системы"
        
        return summary
    
    def _is_important_file(self, file_path: Path) -> bool:
        """Check if file is important enough for memory."""
        important_extensions = {
            '.py', '.js', '.ts', '.go', '.rs',  # Code
            '.md', '.txt', '.doc', '.docx',     # Docs
            '.yaml', '.yml', '.json', '.toml',  # Config
            '.pdf', '.xlsx', '.csv'             # Data
        }
        
        # Skip hidden files and temp files
        if file_path.name.startswith('.') or file_path.name.startswith('~'):
            return False
        
        return file_path.suffix.lower() in important_extensions
    
    def _get_file_type_description(self, file_path: Path) -> str:
        """Get human-readable file type description."""
        ext_map = {
            '.py': 'Python скрипт',
            '.js': 'JavaScript файл',
            '.md': 'Markdown документ',
            '.yaml': 'YAML конфигурация',
            '.json': 'JSON данные',
            '.txt': 'текстовый файл',
            '.pdf': 'PDF документ',
            '.csv': 'CSV таблица'
        }
        
        return ext_map.get(file_path.suffix.lower(), f'{file_path.suffix} файл')
    
    def _human_size(self, size: int) -> str:
        """Convert size to human readable format."""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"
    
    async def _get_file_hash(self, file_path: Path) -> str:
        """Calculate file hash for deduplication."""
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()


async def watch_directory(path: str, bus_client: EventBusClient):
    """Start watching a directory for changes."""
    event_handler = TitanFileHandler(bus_client)
    observer = Observer()
    observer.schedule(event_handler, path, recursive=True)
    
    observer.start()
    logger.info(f"File watcher started for: {path}")
    
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        logger.info("File watcher stopped")
    
    observer.join()


async def main():
    """Main entry point."""
    import sys
    
    # Initialize Event Bus client
    config = EventBusConfig()
    bus_client = EventBusClient(config)
    await bus_client.connect()
    
    # Get watch path from args or default
    watch_path = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser("~/Desktop")
    
    try:
        await watch_directory(watch_path, bus_client)
    finally:
        await bus_client.disconnect()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
