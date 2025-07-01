"""Example: File Watcher Integration with Titan Event Bus."""

import asyncio
import os
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from titan_bus import publish, EventPriority


class TitanFileHandler(FileSystemEventHandler):
    """File system event handler that publishes to Titan Event Bus."""
    
    def __init__(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
    
    def on_created(self, event):
        """Handle file creation."""
        if event.is_directory:
            return
        
        self._publish_event("file_created", event.src_path)
    
    def on_modified(self, event):
        """Handle file modification."""
        if event.is_directory:
            return
        
        self._publish_event("file_modified", event.src_path)
    
    def on_deleted(self, event):
        """Handle file deletion."""
        if event.is_directory:
            return
        
        self._publish_event("file_deleted", event.src_path)
    
    def _publish_event(self, event_type: str, path: str):
        """Publish file event to Titan Event Bus."""
        file_path = Path(path)
        
        # Prepare payload
        payload = {
            "path": str(file_path),
            "name": file_path.name,
            "extension": file_path.suffix,
            "size": file_path.stat().st_size if file_path.exists() else 0,
            "event_source": "file_watcher"
        }
        
        # Determine priority based on file type
        priority = EventPriority.HIGH if file_path.suffix in ['.pdf', '.doc', '.docx'] else EventPriority.MEDIUM
        
        # Publish event
        asyncio.run(publish(
            topic="fs.v1",
            event_type=event_type,
            payload=payload,
            priority=priority
        ))
        
        print(f"Published {event_type} for {file_path.name}")


def watch_directory(path: str):
    """Start watching a directory for changes."""
    event_handler = TitanFileHandler()
    observer = Observer()
    observer.schedule(event_handler, path, recursive=True)
    
    observer.start()
    print(f"Watching directory: {path}")
    
    try:
        while True:
            asyncio.run(asyncio.sleep(1))
    except KeyboardInterrupt:
        observer.stop()
    
    observer.join()


if __name__ == "__main__":
    # Watch Desktop and Downloads
    import sys
    
    watch_path = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser("~/Desktop")
    watch_directory(watch_path)
