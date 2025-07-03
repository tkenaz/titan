#!/usr/bin/env python3
"""Test Goal Scheduler functionality."""

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import httpx
import yaml
from datetime import datetime


async def test_goal_scheduler():
    """Test Goal Scheduler API and functionality."""
    
    base_url = "http://localhost:8005"
    token = os.getenv("ADMIN_TOKEN", "titan-secret-token-change-me-in-production")
    headers = {"Authorization": f"Bearer {token}"}
    
    print("🎯 GOAL SCHEDULER TEST")
    print("=" * 50)
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        # 1. Check health
        print("\n1️⃣ Checking Goal Scheduler health...")
        try:
            response = await client.get(f"{base_url}/health")
            if response.status_code == 200:
                print("   ✅ Goal Scheduler is healthy")
            else:
                print(f"   ❌ Health check failed: {response.status_code}")
                return
        except Exception as e:
            print(f"   ❌ Cannot connect to Goal Scheduler: {e}")
            print("   Run: make scheduler-up")
            return
            
        # 2. List goals
        print("\n2️⃣ Listing configured goals...")
        response = await client.get(f"{base_url}/goals", headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            print(f"   Found {data['total']} goals:")
            
            for goal in data['goals']:
                state_emoji = {
                    "SUCCEEDED": "✅",
                    "FAILED": "❌",
                    "IN_PROGRESS": "🔄",
                    "PENDING": "⏳",
                    "PAUSED": "⏸️",
                    "NO_RUNS": "⚪"
                }.get(goal['state'], "❓")
                
                print(f"   {state_emoji} {goal['id']}: {goal['name']}")
                if goal['schedule']:
                    print(f"      Schedule: {goal['schedule']}")
                if goal['trigger_count'] > 0:
                    print(f"      Triggers: {goal['trigger_count']}")
                if goal['last_run']:
                    print(f"      Last run: {goal['last_run']}")
        else:
            print(f"   ❌ Failed to list goals: {response.status_code}")
            
        # 3. Enable test goal
        print("\n3️⃣ Enabling test goal...")
        test_goal_path = Path("goals/test_goal.yaml")
        
        if test_goal_path.exists():
            # Read and modify
            with open(test_goal_path, 'r') as f:
                goal_data = yaml.safe_load(f)
            
            goal_data['enabled'] = True
            goal_data['schedule'] = "@every 30s"  # Run every 30 seconds
            
            with open(test_goal_path, 'w') as f:
                yaml.dump(goal_data, f, default_flow_style=False)
                
            print("   ✅ Test goal enabled with 30s schedule")
            
            # Reload goals
            print("   Reloading goals...")
            response = await client.post(f"{base_url}/goals/reload", headers=headers)
            if response.status_code == 200:
                print("   ✅ Goals reloaded")
            else:
                print(f"   ❌ Reload failed: {response.status_code}")
        else:
            print("   ⚠️  Test goal not found, creating...")
            # Create test goal
            test_goal = {
                "id": "test_goal",
                "name": "Test Goal",
                "schedule": "@every 30s",
                "steps": [
                    {
                        "id": "echo_test",
                        "type": "plugin",
                        "plugin": "echo",
                        "params": {"message": "Test from Goal Scheduler"}
                    }
                ],
                "enabled": True
            }
            
            with open(test_goal_path, 'w') as f:
                yaml.dump(test_goal, f, default_flow_style=False)
                
            print("   ✅ Test goal created")
            
        # 4. Run goal immediately
        print("\n4️⃣ Running test_goal immediately...")
        response = await client.post(
            f"{base_url}/goals/run",
            headers=headers,
            json={"goal_id": "test_goal"}
        )
        
        if response.status_code == 200:
            data = response.json()
            instance_id = data['instance_id']
            print(f"   ✅ Goal queued: {instance_id}")
            
            # Wait a bit for execution
            await asyncio.sleep(3)
            
            # Check goal details
            print("\n5️⃣ Checking goal execution...")
            response = await client.get(f"{base_url}/goals/test_goal", headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                instances = data['instances']
                
                if instances:
                    latest = instances[0]
                    print(f"   Latest instance: {latest['id']}")
                    print(f"   State: {latest['state']}")
                    print(f"   Current step: {latest['current_step']}")
                    
                    if latest.get('last_error'):
                        print(f"   ❌ Error: {latest['last_error']}")
                    elif latest['state'] == 'SUCCEEDED':
                        print("   ✅ Goal executed successfully!")
                    elif latest['state'] == 'IN_PROGRESS':
                        print("   🔄 Goal still running...")
                else:
                    print("   ⚠️  No instances found")
            else:
                print(f"   ❌ Failed to get goal details: {response.status_code}")
                
        else:
            print(f"   ❌ Failed to run goal: {response.status_code}")
            print(f"   Response: {response.text}")
            
        # 6. Test pause/resume
        print("\n6️⃣ Testing pause/resume (if instance exists)...")
        response = await client.get(f"{base_url}/goals/test_goal", headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            instances = data['instances']
            
            # Find a pending or in-progress instance
            active_instance = None
            for inst in instances:
                if inst['state'] in ['PENDING', 'IN_PROGRESS']:
                    active_instance = inst
                    break
                    
            if active_instance:
                instance_id = active_instance['id']
                
                # Pause
                response = await client.post(
                    f"{base_url}/goals/{instance_id}/pause",
                    headers=headers
                )
                if response.status_code == 200:
                    print(f"   ✅ Instance {instance_id} paused")
                    
                    # Resume
                    await asyncio.sleep(1)
                    response = await client.post(
                        f"{base_url}/goals/{instance_id}/resume",
                        headers=headers
                    )
                    if response.status_code == 200:
                        print(f"   ✅ Instance {instance_id} resumed")
            else:
                print("   ℹ️  No active instances to test pause/resume")
                
        # 7. Cleanup - disable test goal
        print("\n7️⃣ Cleanup - disabling test goal...")
        with open(test_goal_path, 'r') as f:
            goal_data = yaml.safe_load(f)
            
        goal_data['enabled'] = False
        
        with open(test_goal_path, 'w') as f:
            yaml.dump(goal_data, f, default_flow_style=False)
            
        print("   ✅ Test goal disabled")
        
    print("\n✅ Goal Scheduler test completed!")


if __name__ == "__main__":
    asyncio.run(test_goal_scheduler())
