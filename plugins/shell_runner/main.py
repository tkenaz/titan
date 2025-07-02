#!/usr/bin/env python3
"""Shell runner plugin - executes whitelisted commands safely."""

import os
import json
import sys
import subprocess
import shlex
import logging
from typing import List, Tuple

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("shell_runner")

# Hardcoded whitelist (should match plugin.yaml)
ALLOWED_COMMANDS = {
    "ls", "df", "uname", "uptime", "date", "pwd", "whoami", "echo"
}


def validate_command(cmd: str) -> Tuple[bool, str]:
    """Validate command against whitelist."""
    try:
        # Parse command
        parts = shlex.split(cmd)
        if not parts:
            return False, "Empty command"
        
        # Check base command
        base_cmd = parts[0]
        
        # Remove any path components
        if "/" in base_cmd:
            base_cmd = base_cmd.split("/")[-1]
        
        if base_cmd not in ALLOWED_COMMANDS:
            return False, f"Command '{base_cmd}' not in whitelist"
        
        # Additional safety checks
        dangerous_chars = [";", "|", "&", ">", "<", "`", "$", "(", ")", "{", "}"]
        for char in dangerous_chars:
            if char in cmd:
                return False, f"Dangerous character '{char}' detected"
        
        return True, ""
        
    except Exception as e:
        return False, f"Failed to parse command: {e}"


def execute_command(cmd: str, timeout: int = 10) -> Tuple[str, str, int]:
    """Execute command with timeout."""
    try:
        # Run command
        result = subprocess.run(
            shlex.split(cmd),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False
        )
        
        return result.stdout, result.stderr, result.returncode
        
    except subprocess.TimeoutExpired:
        return "", "Command timed out", 124
    except Exception as e:
        return "", str(e), 1


def main():
    """Main plugin entry point."""
    # Get event data from environment
    event_data = os.environ.get("EVENT_DATA")
    if not event_data:
        logger.error("No EVENT_DATA provided")
        sys.exit(1)
    
    try:
        event = json.loads(event_data)
        payload = event.get("payload", {})
        
        # Extract command
        command = payload.get("command", "").strip()
        if not command:
            logger.error("No command provided")
            sys.exit(1)
        
        logger.info(f"Received command: {command}")
        
        # Validate command
        valid, error = validate_command(command)
        if not valid:
            logger.error(f"Command validation failed: {error}")
            
            # Output error result
            result = {
                "event_type": "cmd_result",
                "topic": "system.v1",
                "payload": {
                    "command": command,
                    "success": False,
                    "error": error,
                    "exit_code": 1
                }
            }
            
            print(json.dumps(result, indent=2))
            sys.exit(1)
        
        # Execute command
        stdout, stderr, exit_code = execute_command(command)
        
        # Output result
        result = {
            "event_type": "cmd_result",
            "topic": "system.v1",
            "payload": {
                "command": command,
                "stdout": stdout,
                "stderr": stderr,
                "exit_code": exit_code,
                "success": (exit_code == 0)
            }
        }
        
        print(json.dumps(result, indent=2))
        
        logger.info(f"Command completed with exit code: {exit_code}")
        
    except Exception as e:
        logger.error(f"Plugin error: {e}", exc_info=True)
        
        # Output error result
        error_result = {
            "event_type": "cmd_result",
            "topic": "system.v1",
            "payload": {
                "command": command if 'command' in locals() else "unknown",
                "success": False,
                "error": str(e),
                "exit_code": 1
            }
        }
        
        print(json.dumps(error_result, indent=2))
        sys.exit(1)


if __name__ == "__main__":
    main()
