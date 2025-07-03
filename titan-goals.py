#!/usr/bin/env python3
"""CLI for managing Titan goals."""

import click
import httpx
import yaml
import asyncio
from datetime import datetime
from pathlib import Path
from tabulate import tabulate
import os


BASE_URL = os.getenv("SCHEDULER_API_URL", "http://localhost:8005")
TOKEN = os.getenv("ADMIN_TOKEN", "titan-secret-token-change-me-in-production")


def get_headers():
    """Get authorization headers."""
    return {"Authorization": f"Bearer {TOKEN}"}


@click.group()
def cli():
    """Titan Goal Scheduler CLI."""
    pass


@cli.command()
def list():
    """List all configured goals."""
    async def _list():
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{BASE_URL}/goals", headers=get_headers())
            
            if response.status_code != 200:
                click.echo(f"Error: {response.status_code} - {response.text}", err=True)
                return
                
            data = response.json()
            
            if not data['goals']:
                click.echo("No goals configured")
                return
                
            # Prepare table data
            table_data = []
            for goal in data['goals']:
                state_icon = {
                    "SUCCEEDED": "✅",
                    "FAILED": "❌", 
                    "IN_PROGRESS": "🔄",
                    "PENDING": "⏳",
                    "PAUSED": "⏸️",
                    "NO_RUNS": "⚪"
                }.get(goal['state'], "❓")
                
                table_data.append([
                    goal['id'],
                    goal['name'],
                    "✓" if goal['enabled'] else "✗",
                    f"{state_icon} {goal['state']}",
                    goal['schedule'] or "-",
                    goal['trigger_count'] or 0
                ])
                
            headers = ["ID", "Name", "Enabled", "State", "Schedule", "Triggers"]
            click.echo(tabulate(table_data, headers=headers, tablefmt="grid"))
            
    asyncio.run(_list())


@cli.command()
@click.argument('goal_id')
def show(goal_id):
    """Show detailed information about a goal."""
    async def _show():
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{BASE_URL}/goals/{goal_id}", headers=get_headers())
            
            if response.status_code == 404:
                click.echo(f"Goal '{goal_id}' not found", err=True)
                return
            elif response.status_code != 200:
                click.echo(f"Error: {response.status_code} - {response.text}", err=True)
                return
                
            data = response.json()
            config = data['config']
            instances = data['instances']
            
            # Goal info
            click.echo(f"\n🎯 Goal: {config['name']} ({config['id']})")
            click.echo(f"   Enabled: {'Yes' if config['enabled'] else 'No'}")
            
            if config['schedule']:
                click.echo(f"   Schedule: {config['schedule']}")
                if data['next_run']:
                    click.echo(f"   Next run: {data['next_run']}")
                    
            if config['triggers']:
                click.echo(f"   Triggers: {len(config['triggers'])}")
                for trigger in config['triggers']:
                    click.echo(f"     - {trigger['topic']}")
                    
            # Steps
            click.echo(f"\n📋 Steps ({len(config['steps'])}):")
            for i, step in enumerate(config['steps']):
                click.echo(f"   {i+1}. {step['id']} ({step['type']})")
                if step['type'] == 'plugin':
                    click.echo(f"      Plugin: {step['plugin']}")
                elif step['type'] == 'bus_event':
                    click.echo(f"      Topic: {step['topic']}")
                    
            # Recent instances
            if instances:
                click.echo(f"\n📊 Recent runs ({len(instances)}):")
                for inst in instances[:5]:
                    state_icon = "✅" if inst['state'] == "SUCCEEDED" else "❌" if inst['state'] == "FAILED" else "🔄"
                    started = inst['started_at'] or "Not started"
                    click.echo(f"   {state_icon} {inst['id']} - {started}")
                    
    asyncio.run(_show())


@cli.command()
@click.argument('goal_id')
@click.option('--params', '-p', help='Parameters as JSON string')
def run(goal_id, params):
    """Run a goal immediately."""
    async def _run():
        async with httpx.AsyncClient() as client:
            request_data = {"goal_id": goal_id}
            
            if params:
                try:
                    import json
                    request_data['params'] = json.loads(params)
                except:
                    click.echo("Invalid JSON in params", err=True)
                    return
                    
            response = await client.post(
                f"{BASE_URL}/goals/run", 
                headers=get_headers(),
                json=request_data
            )
            
            if response.status_code == 404:
                click.echo(f"Goal '{goal_id}' not found", err=True)
            elif response.status_code == 200:
                data = response.json()
                click.echo(f"✅ {data['message']}")
                click.echo(f"   Instance ID: {data['instance_id']}")
            else:
                click.echo(f"Error: {response.status_code} - {response.text}", err=True)
                
    asyncio.run(_run())


@cli.command()
def reload():
    """Reload goal configurations from YAML files."""
    async def _reload():
        async with httpx.AsyncClient() as client:
            response = await client.post(f"{BASE_URL}/goals/reload", headers=get_headers())
            
            if response.status_code == 200:
                data = response.json()
                click.echo(f"✅ {data['message']}")
                click.echo(f"   Loaded: {data['loaded']} goals")
                for goal_id in data['goals']:
                    click.echo(f"   - {goal_id}")
            else:
                click.echo(f"Error: {response.status_code} - {response.text}", err=True)
                
    asyncio.run(_reload())


@cli.command()
@click.argument('instance_id')
def pause(instance_id):
    """Pause a running goal instance."""
    async def _pause():
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{BASE_URL}/goals/{instance_id}/pause",
                headers=get_headers()
            )
            
            if response.status_code == 200:
                click.echo(f"⏸️  Goal instance {instance_id} paused")
            else:
                click.echo(f"Error: {response.status_code} - {response.text}", err=True)
                
    asyncio.run(_pause())


@cli.command()
@click.argument('instance_id')
def resume(instance_id):
    """Resume a paused goal instance."""
    async def _resume():
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{BASE_URL}/goals/{instance_id}/resume",
                headers=get_headers()
            )
            
            if response.status_code == 200:
                click.echo(f"▶️  Goal instance {instance_id} resumed")
            else:
                click.echo(f"Error: {response.status_code} - {response.text}", err=True)
                
    asyncio.run(_resume())


@cli.command()
@click.argument('goal_file', type=click.Path(exists=True))
def validate(goal_file):
    """Validate a goal YAML file."""
    try:
        with open(goal_file, 'r') as f:
            data = yaml.safe_load(f)
            
        # Basic validation
        required_fields = ['id', 'name', 'steps']
        missing = [f for f in required_fields if f not in data]
        
        if missing:
            click.echo(f"❌ Missing required fields: {', '.join(missing)}", err=True)
            return
            
        if not data.get('schedule') and not data.get('triggers'):
            click.echo("❌ Either 'schedule' or 'triggers' must be specified", err=True)
            return
            
        # Validate steps
        for i, step in enumerate(data.get('steps', [])):
            if 'id' not in step:
                click.echo(f"❌ Step {i} missing 'id'", err=True)
                return
            if 'type' not in step:
                click.echo(f"❌ Step {i} missing 'type'", err=True)
                return
                
        click.echo(f"✅ Goal file '{goal_file}' is valid")
        click.echo(f"   ID: {data['id']}")
        click.echo(f"   Name: {data['name']}")
        click.echo(f"   Steps: {len(data.get('steps', []))}")
        
    except yaml.YAMLError as e:
        click.echo(f"❌ Invalid YAML: {e}", err=True)
    except Exception as e:
        click.echo(f"❌ Error: {e}", err=True)


if __name__ == '__main__':
    cli()
