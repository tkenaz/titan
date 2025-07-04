#!/usr/bin/env python3
"""
Fix CORS in all services by making auth skip OPTIONS requests
"""

import os
import re

services = [
    "memory_service/api.py",
    "plugin_manager/api.py", 
    "goal_scheduler/api.py",
]

for service_file in services:
    if not os.path.exists(service_file):
        print(f"Skipping {service_file} - not found")
        continue
        
    print(f"Fixing {service_file}...")
    
    with open(service_file, 'r') as f:
        content = f.read()
    
    # Find the verify_token function
    if "async def verify_token" in content:
        # Add Request import
        if "from fastapi import" in content and ", Request" not in content:
            content = content.replace(
                "from fastapi import",
                "from fastapi import Request,"
            )
        
        # Modify verify_token to accept request and skip OPTIONS
        old_pattern = r'async def verify_token\(credentials: HTTPAuthorizationCredentials = Depends\(security\)\) -> str:'
        new_pattern = 'async def verify_token(request: Request, credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> Optional[str]:'
        content = re.sub(old_pattern, new_pattern, content)
        
        # Add OPTIONS check at the beginning of verify_token
        verify_token_body = """async def verify_token(request: Request, credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> Optional[str]:
    \"\"\"Verify Bearer token.\"\"\"
    # Skip auth for OPTIONS requests (CORS preflight)
    if request.method == "OPTIONS":
        return None
        
    if not credentials:
        raise HTTPException(
            status_code=401,
            detail="Missing authorization header"
        )
    
    token = credentials.credentials"""
        
        # Replace the function
        pattern = r'async def verify_token.*?token = credentials\.credentials'
        content = re.sub(pattern, verify_token_body, content, flags=re.DOTALL)
        
        # Fix Optional import
        if "from typing import" in content and "Optional" not in content:
            content = content.replace(
                "from typing import",
                "from typing import Optional,"
            )
    
    with open(service_file, 'w') as f:
        f.write(content)
    
    print(f"Fixed {service_file}")

print("\nNow rebuild Docker images and restart services!")
