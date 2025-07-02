"""Sandbox executor for running plugins in isolated containers."""

import asyncio
import json
import logging
import tempfile
import time
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from plugin_manager.config import SandboxConfig
from plugin_manager.models import PluginConfig, PluginResult, PluginTask


logger = logging.getLogger(__name__)


class SandboxExecutor:
    """Execute plugins in sandboxed Docker/Podman containers."""
    
    def __init__(self, config: SandboxConfig):
        self.config = config
        self.runtime = config.runtime  # docker or podman
        
    async def execute(
        self,
        plugin_config: PluginConfig,
        plugin_path: Path,
        task: PluginTask
    ) -> PluginResult:
        """Execute plugin in sandbox."""
        start_time = time.time()
        
        try:
            # Prepare container
            container_name = f"titan-plugin-{plugin_config.name}-{task.event_id[:8]}"
            
            # Build command
            cmd = self._build_container_command(
                container_name,
                plugin_config,
                plugin_path,
                task
            )
            
            # Execute
            stdout, stderr, exit_code = await self._run_container(cmd)
            
            # Parse output
            duration_ms = (time.time() - start_time) * 1000
            
            return PluginResult(
                plugin_name=plugin_config.name,
                event_id=task.event_id,
                success=(exit_code == 0),
                stdout=stdout,
                stderr=stderr,
                exit_code=exit_code,
                duration_ms=duration_ms
            )
            
        except asyncio.TimeoutError:
            logger.error(f"Plugin {plugin_config.name} timed out")
            return PluginResult(
                plugin_name=plugin_config.name,
                event_id=task.event_id,
                success=False,
                error=f"Timeout after {self.config.timeout_sec}s",
                duration_ms=(time.time() - start_time) * 1000
            )
            
        except Exception as e:
            logger.error(f"Plugin {plugin_config.name} failed: {e}")
            return PluginResult(
                plugin_name=plugin_config.name,
                event_id=task.event_id,
                success=False,
                error=str(e),
                duration_ms=(time.time() - start_time) * 1000
            )
    
    def _build_container_command(
        self,
        container_name: str,
        plugin_config: PluginConfig,
        plugin_path: Path,
        task: PluginTask
    ) -> List[str]:
        """Build container execution command."""
        cmd = [
            self.runtime, "run",
            "--rm",  # Remove after exit
            "--name", container_name,
            
            # Security
            "--network", self.config.network_mode,
            "--read-only" if self.config.read_only else "",
            "--security-opt", "no-new-privileges",
            
            # Resources
            "--cpus", self._convert_cpu_units(plugin_config.resources.cpu),
            "--memory", self._convert_memory_units(plugin_config.resources.memory),
            
            # Temp storage
            "--tmpfs", f"/tmp:size={self._convert_memory_units(self.config.tmp_size)}",
            
            # Working directory
            "--workdir", self.config.work_dir,
        ]
        
        # Drop capabilities
        for cap in self.config.drop_capabilities:
            cmd.extend(["--cap-drop", cap])
        
        # Mount plugin code
        # Convert container path to host path if needed
        host_plugins_path = os.environ.get('HOST_PLUGINS_PATH')
        if host_plugins_path and str(plugin_path).startswith('/app/plugins/'):
            # Replace /app/plugins/ with actual host path
            plugin_name = plugin_path.name
            host_plugin_path = Path(host_plugins_path) / plugin_name
            mount_path = str(host_plugin_path.absolute())
        else:
            mount_path = str(plugin_path.absolute())
            
        cmd.extend([
            "-v", f"{mount_path}:{self.config.work_dir}:ro"
        ])
        
        # Mount allowed paths (if any)
        if plugin_config.permissions.fs:
            mounted_paths = set()  # To avoid duplicates
            for allow_path in plugin_config.permissions.fs.allow:
                # Convert glob to actual path for mounting
                base_path = allow_path.rstrip("/**/*").rstrip("/**").rstrip("/*")
                
                # For the titan project, mount the whole directory
                if "titan" in base_path:
                    base_path = "/Users/mvyshhnyvetska/Desktop/titan"
                
                if Path(base_path).exists() and base_path not in mounted_paths:
                    cmd.extend(["-v", f"{base_path}:{base_path}:ro"])
                    mounted_paths.add(base_path)
                    logger.debug(f"Mounting path: {base_path}")
        
        # Environment variables
        cmd.extend([
            "-e", f"PLUGIN_NAME={plugin_config.name}",
            "-e", f"PLUGIN_VERSION={plugin_config.version}",
            "-e", f"EVENT_ID={task.event_id}",
            "-e", f"EVENT_DATA={json.dumps(task.event)}",
        ])
        
        # Image and entrypoint
        cmd.append(plugin_config.image)
        
        # Entrypoint command
        entrypoint_parts = plugin_config.entrypoint.split()
        cmd.extend(entrypoint_parts)
        
        # Filter out empty strings
        return [c for c in cmd if c]
    
    def _convert_cpu_units(self, cpu: str) -> str:
        """Convert Kubernetes CPU units to Docker format."""
        if cpu.endswith("m"):
            # Convert millicores to cores
            millicores = int(cpu[:-1])
            return str(millicores / 1000)
        return cpu
    
    def _convert_memory_units(self, memory: str) -> str:
        """Convert Kubernetes memory units to Docker format."""
        if memory.endswith("Mi"):
            # Convert Mi to m (lowercase)
            return memory[:-2] + "m"
        elif memory.endswith("Gi"):
            # Convert Gi to g
            return memory[:-2] + "g"
        elif memory.endswith("Ki"):
            # Convert Ki to k
            return memory[:-2] + "k"
        return memory
    
    async def _run_container(
        self,
        cmd: List[str]
    ) -> Tuple[str, str, int]:
        """Run container command with timeout."""
        logger.debug(f"Running command: {' '.join(cmd)}")
        
        # Create subprocess
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        try:
            # Wait with timeout
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=self.config.timeout_sec
            )
            
            return (
                stdout.decode("utf-8", errors="replace"),
                stderr.decode("utf-8", errors="replace"),
                proc.returncode or 0
            )
            
        except asyncio.TimeoutError:
            # Kill the container
            logger.warning(f"Killing timed out container")
            try:
                kill_cmd = [self.runtime, "kill", cmd[4]]  # container name is at index 4
                await asyncio.create_subprocess_exec(*kill_cmd)
            except Exception as e:
                logger.error(f"Failed to kill container: {e}")
            
            raise
    
    async def prepare_plugin_image(
        self,
        plugin_config: PluginConfig,
        plugin_path: Path
    ) -> bool:
        """Prepare Docker image for plugin (install requirements)."""
        if not plugin_config.requirements:
            return True
        
        # For Python plugins with requirements, we need to build a custom image
        # This is a simplified version - in production use proper Dockerfile
        
        dockerfile_content = f"""
FROM {plugin_config.image}
WORKDIR {self.config.work_dir}
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
"""
        
        # Write requirements
        req_file = plugin_path / "requirements.txt"
        req_file.write_text("\n".join(plugin_config.requirements))
        
        # Write Dockerfile
        dockerfile = plugin_path / "Dockerfile.generated"
        dockerfile.write_text(dockerfile_content)
        
        # Build image
        image_name = f"titan-plugin-{plugin_config.name}:{plugin_config.version}"
        
        cmd = [
            self.runtime, "build",
            "-t", image_name,
            "-f", str(dockerfile),
            str(plugin_path)
        ]
        
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await proc.communicate()
        
        if proc.returncode != 0:
            logger.error(f"Failed to build image: {stderr.decode()}")
            return False
        
        # Update plugin config to use custom image
        plugin_config.image = image_name
        return True
