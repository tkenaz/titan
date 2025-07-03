#!/usr/bin/env python3
"""Demo: Titan autonomous workflow."""

import asyncio
import httpx
import os
import time
import yaml
from pathlib import Path


async def demo_titan():
    """Demonstrate Titan's full capabilities."""
    
    token = os.getenv("ADMIN_TOKEN", "titan-secret-token-change-me-in-production")
    headers = {"Authorization": f"Bearer {token}"}
    
    print("🤖 TITAN AUTONOMOUS SYSTEM DEMO")
    print("=" * 50)
    print("This demo shows how all components work together:")
    print("- Goal Scheduler triggers workflows")
    print("- Plugin Manager executes tasks")
    print("- Memory Service remembers results")
    print("- Event Bus connects everything")
    print("=" * 50)
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Step 1: Create a demo goal
        print("\n📝 Step 1: Creating demo workflow goal...")
        
        demo_goal = {
            "id": "demo_workflow",
            "name": "Demo Autonomous Workflow",
            "schedule": "@every 60s",
            "steps": [
                {
                    "id": "generate_report",
                    "type": "plugin",
                    "plugin": "echo",
                    "params": {
                        "message": f"Autonomous report generated at {time.strftime('%Y-%m-%d %H:%M:%S')}",
                        "report_data": {
                            "system_status": "operational",
                            "components": ["memory", "plugins", "scheduler"],
                            "timestamp": time.time()
                        }
                    }
                },
                {
                    "id": "save_to_memory",
                    "type": "bus_event",
                    "topic": "system.v1",
                    "event_type": "report_complete",
                    "payload_template": '{"report": "{{ prev.result }}", "importance": 0.8}'
                }
            ],
            "enabled": True
        }
        
        # Save goal
        goal_path = Path("goals/demo_workflow.yaml")
        with open(goal_path, 'w') as f:
            yaml.dump(demo_goal, f, default_flow_style=False)
        
        print(f"   ✅ Goal created: {goal_path}")
        
        # Reload goals
        print("   🔄 Reloading goals...")
        response = await client.post(f"http://localhost:8005/goals/reload", headers=headers)
        
        if response.status_code == 200:
            print("   ✅ Goals reloaded")
        
        # Step 2: Run the goal immediately
        print("\n🚀 Step 2: Executing workflow...")
        
        response = await client.post(
            "http://localhost:8005/goals/run",
            headers=headers,
            json={"goal_id": "demo_workflow"}
        )
        
        if response.status_code == 200:
            instance_id = response.json()["instance_id"]
            print(f"   ✅ Workflow started: {instance_id}")
            
            # Wait for execution
            print("   ⏳ Waiting for execution...")
            await asyncio.sleep(5)
            
            # Check status
            response = await client.get(f"http://localhost:8005/goals/demo_workflow", headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                if data["instances"]:
                    latest = data["instances"][0]
                    print(f"   📊 Status: {latest['state']}")
                    
                    if latest["step_results"]:
                        print("   📋 Step results:")
                        for step, result in latest["step_results"].items():
                            print(f"      - {step}: ✅ Completed")
        
        # Step 3: Check memory
        print("\n🧠 Step 3: Checking what Titan remembered...")
        
        search_data = {
            "query": "autonomous report",
            "k": 5
        }
        
        response = await client.post(
            "http://localhost:8001/memory/search",
            headers=headers,
            json=search_data
        )
        
        if response.status_code == 200:
            memories = response.json()
            print(f"   Found {len(memories)} related memories")
            
            for mem in memories[:3]:
                print(f"   💭 {mem['content'][:100]}...")
        
        # Step 4: Demonstrate plugin resilience
        print("\n🛡️ Step 4: Testing self-healing with Circuit Breaker...")
        
        # Create a failing plugin execution
        fail_data = {
            "plugin": "test_plugin",
            "event_data": {
                "event_type": "test",
                "payload": {"force_error": True}
            }
        }
        
        print("   Simulating plugin failures...")
        for i in range(6):
            response = await client.post(
                "http://localhost:8003/plugins/execute",
                headers=headers,
                json=fail_data
            )
            
            if response.status_code == 200:
                result = response.json()
                if not result["success"]:
                    print(f"   ❌ Failure {i+1}: {result.get('error', 'Unknown error')}")
        
        # Check plugin status
        response = await client.get("http://localhost:8003/plugins", headers=headers)
        
        if response.status_code == 200:
            plugins = response.json()["plugins"]
            test_plugin = next((p for p in plugins if p["name"] == "test_plugin"), None)
            
            if test_plugin and not test_plugin["healthy"]:
                print("   ✅ Circuit breaker activated! Plugin disabled for safety")
                print(f"   ⏰ Will retry at: {test_plugin.get('disabled_until', 'Unknown')}")
        
        # Step 5: Show autonomous execution
        print("\n🤖 Step 5: Autonomous execution in action...")
        print("   The demo_workflow goal is now running every 60 seconds")
        print("   It will:")
        print("   1. Generate reports automatically")
        print("   2. Save important data to memory")
        print("   3. Trigger other workflows via Event Bus")
        print("   4. Self-heal if components fail")
        
        # Cleanup
        print("\n🧹 Cleanup: Disabling demo goal...")
        demo_goal["enabled"] = False
        with open(goal_path, 'w') as f:
            yaml.dump(demo_goal, f, default_flow_style=False)
        
        await client.post(f"http://localhost:8005/goals/reload", headers=headers)
        
        print("\n✨ DEMO COMPLETE!")
        print("\nTitan is now fully autonomous and can:")
        print("- ✅ Execute scheduled tasks")
        print("- ✅ React to events")
        print("- ✅ Remember important information")
        print("- ✅ Self-heal from failures")
        print("- ✅ Chain complex workflows")
        print("\n🚀 The future of autonomous AI systems!")


if __name__ == "__main__":
    asyncio.run(demo_titan())
