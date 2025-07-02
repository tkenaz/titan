#!/usr/bin/env python3
"""CLI for Titan Plugin Manager."""

import click
import httpx
import json
from tabulate import tabulate


API_BASE = "http://localhost:8003"


@click.group()
def cli():
    """Titan Plugin Manager CLI."""
    pass


@cli.command()
def list():
    """List all loaded plugins."""
    try:
        response = httpx.get(f"{API_BASE}/plugins")
        response.raise_for_status()
        
        data = response.json()
        plugins = data["plugins"]
        
        if not plugins:
            click.echo("No plugins loaded")
            return
        
        # Format as table
        rows = []
        for name, info in plugins.items():
            rows.append([
                name,
                info["version"],
                info["status"],
                info["invocations"],
                info["errors"],
                info["last_run"] or "Never"
            ])
        
        headers = ["Name", "Version", "Status", "Invocations", "Errors", "Last Run"]
        click.echo(tabulate(rows, headers=headers, tablefmt="grid"))
        
    except httpx.HTTPError as e:
        click.echo(f"Error: {e}", err=True)
    except Exception as e:
        click.echo(f"Failed to list plugins: {e}", err=True)


@cli.command()
def reload():
    """Hot reload all plugins."""
    try:
        response = httpx.post(f"{API_BASE}/plugins/reload")
        response.raise_for_status()
        
        data = response.json()
        click.echo(f"✅ Reloaded {len(data['plugins'])} plugins:")
        for plugin in data['plugins']:
            click.echo(f"  - {plugin}")
            
    except httpx.HTTPError as e:
        click.echo(f"Error: {e}", err=True)
    except Exception as e:
        click.echo(f"Failed to reload plugins: {e}", err=True)


@cli.command()
@click.argument('plugin_name')
@click.option('--lines', '-n', default=100, help='Number of log lines to show')
def logs(plugin_name: str, lines: int):
    """Show logs for a plugin."""
    try:
        response = httpx.get(
            f"{API_BASE}/plugins/{plugin_name}/logs",
            params={"lines": lines}
        )
        response.raise_for_status()
        
        click.echo(response.text)
        
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            click.echo(f"Plugin '{plugin_name}' not found", err=True)
        else:
            click.echo(f"Error: {e}", err=True)
    except Exception as e:
        click.echo(f"Failed to get logs: {e}", err=True)


@cli.command()
@click.argument('plugin_name')
@click.option('--event', '-e', required=True, help='Event data as JSON')
def trigger(plugin_name: str, event: str):
    """Manually trigger a plugin."""
    try:
        # Parse event JSON
        try:
            event_data = json.loads(event)
        except json.JSONDecodeError:
            click.echo("Invalid JSON for event data", err=True)
            return
        
        # Send request
        response = httpx.post(
            f"{API_BASE}/plugins/trigger",
            json={
                "plugin_name": plugin_name,
                "event_data": event_data
            },
            timeout=120.0  # Long timeout for plugin execution
        )
        response.raise_for_status()
        
        result = response.json()
        
        # Display result
        click.echo(f"\n✅ Plugin executed: {result['success']}")
        click.echo(f"Duration: {result['duration_ms']:.1f}ms")
        
        if result.get('stdout'):
            click.echo("\n📤 STDOUT:")
            click.echo(result['stdout'])
        
        if result.get('stderr'):
            click.echo("\n📥 STDERR:")
            click.echo(result['stderr'])
        
        if result.get('error'):
            click.echo(f"\n❌ Error: {result['error']}")
            
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            click.echo(f"Plugin '{plugin_name}' not found", err=True)
        else:
            click.echo(f"Error: {e}", err=True)
    except Exception as e:
        click.echo(f"Failed to trigger plugin: {e}", err=True)


@cli.command()
def health():
    """Check Plugin Manager health."""
    try:
        response = httpx.get(f"{API_BASE}/health")
        response.raise_for_status()
        
        data = response.json()
        click.echo(f"✅ Plugin Manager is {data['status']}")
        
    except Exception as e:
        click.echo(f"❌ Plugin Manager is not responding: {e}", err=True)


# Example commands group
@cli.group()
def examples():
    """Show example commands."""
    pass


@examples.command('file')
def example_file():
    """Show file_watcher trigger example."""
    example = {
        "event_id": "example-001",
        "topic": "fs.v1",
        "event_type": "file_created",
        "timestamp": "2025-01-01T00:00:00Z",
        "payload": {
            "path": "/Users/mvyshhnyvetska/Downloads/document.pdf",
            "mime_type": "application/pdf"
        }
    }
    
    click.echo("Example command to trigger file_watcher:")
    click.echo(f"\ntitan-plugins trigger file_watcher -e '{json.dumps(example)}'")


@examples.command('shell')
def example_shell():
    """Show shell_runner trigger example."""
    example = {
        "event_id": "example-002",
        "topic": "system.v1",
        "event_type": "run_cmd",
        "timestamp": "2025-01-01T00:00:00Z",
        "payload": {
            "command": "uname -a"
        }
    }
    
    click.echo("Example command to trigger shell_runner:")
    click.echo(f"\ntitan-plugins trigger shell_runner -e '{json.dumps(example)}'")


if __name__ == "__main__":
    cli()
