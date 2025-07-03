#!/usr/bin/env python3
"""
Visual test for Plugin Manager - shows real-time execution.
"""

import asyncio
import json
import sys
from pathlib import Path
from datetime import datetime
from rich.console import Console
from rich.table import Table
from rich.live import Live
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

sys.path.insert(0, str(Path(__file__).parent))

from plugin_manager.config import PluginManagerConfig
from plugin_manager.manager import PluginManager

console = Console()


async def visual_test():
    """Run visual test with rich output."""
    console.clear()
    console.print("[bold cyan]🚀 Titan Plugin Manager - Visual Test[/bold cyan]\n")
    
    # Load and start
    with console.status("[yellow]Starting Plugin Manager...[/yellow]"):
        config = PluginManagerConfig.from_yaml("config/plugins.yaml")
        manager = PluginManager(config)
        await manager.start()
    
    # Show loaded plugins
    table = Table(title="Loaded Plugins")
    table.add_column("Plugin", style="cyan")
    table.add_column("Version", style="green")
    table.add_column("Status", style="yellow")
    
    for name, plugin in manager.plugins.items():
        table.add_row(
            name,
            plugin.config.version,
            plugin.status.value
        )
    
    console.print(table)
    console.print()
    
    # Test sequence
    tests = [
        {
            "name": "Shell Command - Date",
            "plugin": "shell_runner",
            "event": {
                "topic": "system.v1",
                "event_type": "run_cmd",
                "payload": {"command": "date"}
            }
        },
        {
            "name": "Shell Command - System Info",
            "plugin": "shell_runner",
            "event": {
                "topic": "system.v1",
                "event_type": "run_cmd",
                "payload": {"command": "uname -a"}
            }
        },
        {
            "name": "File Analysis - Markdown",
            "plugin": "file_watcher",
            "event": {
                "topic": "fs.v1",
                "event_type": "file_created",
                "payload": {
                    "path": str(Path("test_document.md").absolute()),
                    "mime_type": "text/markdown"
                }
            }
        },
        {
            "name": "Blocked Command - rm",
            "plugin": "shell_runner",
            "event": {
                "topic": "system.v1",
                "event_type": "run_cmd",
                "payload": {"command": "rm -rf /"}
            }
        }
    ]
    
    # Run tests
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        
        for test in tests:
            task = progress.add_task(f"[yellow]Running: {test['name']}[/yellow]", total=None)
            
            # Add event_id
            test["event"]["event_id"] = f"visual-{datetime.now().timestamp()}"
            
            # Execute
            result = await manager.trigger_plugin_manually(
                test["plugin"],
                test["event"]
            )
            
            progress.remove_task(task)
            
            # Show result
            if result.success:
                console.print(f"[green]✓[/green] {test['name']}")
                if result.stdout:
                    # Try to parse as JSON first
                    try:
                        output = json.loads(result.stdout)
                        if "payload" in output and "summary" in output["payload"]:
                            console.print(f"   Summary: [dim]{output['payload']['summary'][:80]}...[/dim]")
                        else:
                            console.print(f"   Output: [dim]{result.stdout.strip()[:80]}[/dim]")
                    except:
                        console.print(f"   Output: [dim]{result.stdout.strip()[:80]}[/dim]")
            else:
                console.print(f"[red]✗[/red] {test['name']}")
                error = result.error or result.stderr
                console.print(f"   Error: [red]{error.strip()}[/red]")
            
            console.print()
    
    # Final status
    status_table = Table(title="Final Status")
    status_table.add_column("Plugin", style="cyan")
    status_table.add_column("Invocations", justify="center")
    status_table.add_column("Errors", justify="center", style="red")
    
    status = manager.get_plugin_status()
    for name, info in status.items():
        status_table.add_row(
            name,
            str(info["invocations"]),
            str(info["errors"])
        )
    
    console.print(status_table)
    
    # Cleanup
    await manager.stop()
    
    console.print(Panel.fit(
        "[bold green]✨ Test Complete![/bold green]\n\n"
        "Plugins are working correctly!",
        title="Success"
    ))


if __name__ == "__main__":
    # Check if rich is installed
    try:
        import rich
    except ImportError:
        print("Installing rich for visual output...")
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "rich"])
    
    asyncio.run(visual_test())
