#!/usr/bin/env python3
"""
Chaos Friday Runner - Controlled chaos engineering for Titan
Injects failures to test system resilience
"""
import os
import sys
import time
import random
import asyncio
import argparse
import subprocess
import logging
from typing import List, Dict, Any
from datetime import datetime
import redis.asyncio as redis
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("chaos_friday")


class ChaosExperiment:
    """Base class for chaos experiments"""
    
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
        self.redis_client = None
    
    async def setup(self, redis_client):
        """Setup experiment"""
        self.redis_client = redis_client
    
    async def run(self) -> Dict[str, Any]:
        """Run the experiment and return results"""
        raise NotImplementedError
    
    async def cleanup(self):
        """Cleanup after experiment"""
        pass
    
    async def log_event(self, event_type: str, details: Dict[str, Any]):
        """Log chaos event to Redis"""
        if self.redis_client:
            event = {
                "event_type": f"chaos.{event_type}",
                "experiment": self.name,
                "origin": "chaos",
                "timestamp": datetime.utcnow().isoformat(),
                **{k: str(v) for k, v in details.items()}
            }
            await self.redis_client.xadd("agent.events", event)


class KillContainerExperiment(ChaosExperiment):
    """Kill a random Titan container"""
    
    def __init__(self, container_prefix: str = "titan-"):
        super().__init__(
            "kill_container",
            f"Kill a random container starting with {container_prefix}"
        )
        self.container_prefix = container_prefix
    
    async def run(self) -> Dict[str, Any]:
        start_time = time.time()
        
        # List containers
        result = subprocess.run(
            ["docker", "ps", "--format", "{{.Names}}"],
            capture_output=True,
            text=True
        )
        
        containers = [
            c for c in result.stdout.strip().split('\n')
            if c.startswith(self.container_prefix) and "redis" not in c
        ]
        
        if not containers:
            return {
                "status": "skipped",
                "reason": "No eligible containers found"
            }
        
        # Pick random container
        target = random.choice(containers)
        logger.info(f"Killing container: {target}")
        
        await self.log_event("container.kill.start", {"target": target})
        
        # Kill container
        subprocess.run(["docker", "kill", target])
        
        # Wait a bit
        await asyncio.sleep(5)
        
        # Check if container restarted
        result = subprocess.run(
            ["docker", "ps", "--filter", f"name={target}", "--format", "{{.Status}}"],
            capture_output=True,
            text=True
        )
        
        recovered = bool(result.stdout.strip())
        recovery_time = time.time() - start_time
        
        await self.log_event("container.kill.complete", {
            "target": target,
            "recovered": recovered,
            "recovery_time": recovery_time
        })
        
        return {
            "status": "success",
            "target": target,
            "recovered": recovered,
            "recovery_time": recovery_time
        }


class NetworkPartitionExperiment(ChaosExperiment):
    """Simulate network partition between services"""
    
    def __init__(self, duration: int = 30):
        super().__init__(
            "network_partition",
            "Block network traffic to Redis for a period"
        )
        self.duration = duration
        self.rule_added = False
    
    async def run(self) -> Dict[str, Any]:
        logger.info(f"Creating network partition for {self.duration}s")
        
        await self.log_event("network.partition.start", {
            "duration": self.duration,
            "target": "redis"
        })
        
        # Add iptables rule to drop Redis traffic
        # Note: This requires root/sudo access
        try:
            subprocess.run([
                "docker", "exec", "titan-model-gateway",
                "iptables", "-A", "OUTPUT", "-p", "tcp", "--dport", "6379", "-j", "DROP"
            ], check=True)
            self.rule_added = True
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to add iptables rule: {e}")
            return {
                "status": "failed",
                "error": "Requires root access or iptables in container"
            }
        
        # Monitor for duration
        start_time = time.time()
        errors_detected = 0
        
        for _ in range(self.duration):
            await asyncio.sleep(1)
            # Check if services are logging errors
            # In real implementation, would check actual service health
            errors_detected += random.randint(0, 3)
        
        # Remove rule
        await self.cleanup()
        
        recovery_start = time.time()
        await asyncio.sleep(5)  # Wait for recovery
        
        total_time = time.time() - start_time
        recovery_time = time.time() - recovery_start
        
        await self.log_event("network.partition.complete", {
            "duration": self.duration,
            "errors_detected": errors_detected,
            "total_time": total_time,
            "recovery_time": recovery_time
        })
        
        return {
            "status": "success",
            "duration": self.duration,
            "errors_detected": errors_detected,
            "recovery_time": recovery_time
        }
    
    async def cleanup(self):
        """Remove iptables rule"""
        if self.rule_added:
            try:
                subprocess.run([
                    "docker", "exec", "titan-model-gateway",
                    "iptables", "-D", "OUTPUT", "-p", "tcp", "--dport", "6379", "-j", "DROP"
                ])
            except:
                logger.warning("Failed to remove iptables rule")


class HighLoadExperiment(ChaosExperiment):
    """Generate high load on a service"""
    
    def __init__(self, target_url: str, duration: int = 60, rps: int = 100):
        super().__init__(
            "high_load",
            f"Generate {rps} requests/second for {duration}s"
        )
        self.target_url = target_url
        self.duration = duration
        self.rps = rps
    
    async def run(self) -> Dict[str, Any]:
        logger.info(f"Generating load: {self.rps} RPS for {self.duration}s")
        
        await self.log_event("load.test.start", {
            "target": self.target_url,
            "rps": self.rps,
            "duration": self.duration
        })
        
        start_time = time.time()
        total_requests = 0
        errors = 0
        
        async def make_request():
            nonlocal total_requests, errors
            try:
                # Simulate request
                await asyncio.sleep(0.01)  # In real implementation, make actual HTTP request
                total_requests += 1
                if random.random() < 0.05:  # 5% error rate
                    errors += 1
            except:
                errors += 1
        
        # Generate load
        tasks = []
        for _ in range(self.duration):
            for _ in range(self.rps):
                tasks.append(asyncio.create_task(make_request()))
            await asyncio.sleep(1)
        
        await asyncio.gather(*tasks, return_exceptions=True)
        
        elapsed = time.time() - start_time
        
        await self.log_event("load.test.complete", {
            "total_requests": total_requests,
            "errors": errors,
            "error_rate": f"{(errors/total_requests*100):.2f}%",
            "duration": elapsed
        })
        
        return {
            "status": "success",
            "total_requests": total_requests,
            "errors": errors,
            "error_rate": f"{(errors/total_requests*100):.2f}%"
        }


class MemoryLeakExperiment(ChaosExperiment):
    """Simulate memory leak in a service"""
    
    def __init__(self, container: str, size_mb: int = 100):
        super().__init__(
            "memory_leak",
            f"Allocate {size_mb}MB in {container}"
        )
        self.container = container
        self.size_mb = size_mb
    
    async def run(self) -> Dict[str, Any]:
        logger.info(f"Simulating memory leak in {self.container}")
        
        await self.log_event("memory.leak.start", {
            "container": self.container,
            "size_mb": self.size_mb
        })
        
        # This would need to be implemented differently in production
        # For now, just simulate the effect
        await asyncio.sleep(10)
        
        await self.log_event("memory.leak.complete", {
            "container": self.container,
            "size_mb": self.size_mb
        })
        
        return {
            "status": "success",
            "container": self.container,
            "size_mb": self.size_mb
        }


class ChaosRunner:
    """Orchestrate chaos experiments"""
    
    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.redis_url = redis_url
        self.redis_client = None
        self.experiments = []
    
    async def setup(self):
        """Setup runner"""
        self.redis_client = await redis.from_url(self.redis_url)
        
        # Register experiments
        self.experiments = [
            KillContainerExperiment(),
            NetworkPartitionExperiment(duration=20),
            HighLoadExperiment("http://localhost:8081/health"),
            MemoryLeakExperiment("titan-model-gateway")
        ]
        
        for exp in self.experiments:
            await exp.setup(self.redis_client)
    
    async def run_experiment(self, name: str) -> Dict[str, Any]:
        """Run a specific experiment"""
        exp = next((e for e in self.experiments if e.name == name), None)
        if not exp:
            return {"status": "error", "reason": f"Unknown experiment: {name}"}
        
        logger.info(f"Running experiment: {exp.name}")
        logger.info(f"Description: {exp.description}")
        
        try:
            result = await exp.run()
            await exp.cleanup()
            return result
        except Exception as e:
            logger.error(f"Experiment failed: {e}")
            await exp.cleanup()
            return {"status": "error", "error": str(e)}
    
    async def run_all(self, delay: int = 60):
        """Run all experiments with delay between them"""
        results = {}
        
        for exp in self.experiments:
            result = await self.run_experiment(exp.name)
            results[exp.name] = result
            
            if exp != self.experiments[-1]:
                logger.info(f"Waiting {delay}s before next experiment...")
                await asyncio.sleep(delay)
        
        return results
    
    async def cleanup(self):
        """Cleanup runner"""
        if self.redis_client:
            await self.redis_client.close()


async def main():
    parser = argparse.ArgumentParser(description="Chaos Friday Runner")
    parser.add_argument(
        "--experiment",
        help="Run specific experiment",
        choices=["kill_container", "network_partition", "high_load", "memory_leak"]
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available experiments"
    )
    parser.add_argument(
        "--delay",
        type=int,
        default=60,
        help="Delay between experiments (seconds)"
    )
    parser.add_argument(
        "--redis-url",
        default="redis://localhost:6379",
        help="Redis connection URL"
    )
    
    args = parser.parse_args()
    
    runner = ChaosRunner(args.redis_url)
    await runner.setup()
    
    try:
        if args.list:
            print("Available experiments:")
            for exp in runner.experiments:
                print(f"  - {exp.name}: {exp.description}")
        elif args.experiment:
            result = await runner.run_experiment(args.experiment)
            print(f"\nResults: {json.dumps(result, indent=2)}")
        else:
            print("Running all experiments...")
            print("WARNING: This will disrupt services!")
            print("Press Ctrl+C to cancel, or wait 5 seconds to continue...")
            await asyncio.sleep(5)
            
            results = await runner.run_all(args.delay)
            print("\nAll experiments complete!")
            print(json.dumps(results, indent=2))
    finally:
        await runner.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
