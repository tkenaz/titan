#!/bin/bash
# Add CORS to all services

echo "Adding CORS middleware to all services..."

# Memory Service
echo "Patching Memory Service..."
cat > /tmp/cors_patch.py << 'EOF'
import sys
import re

# Read the file
with open(sys.argv[1], 'r') as f:
    content = f.read()

# Check if CORS already added
if 'CORSMiddleware' in content:
    print("CORS already added")
    sys.exit(0)

# Add import
if 'from fastapi import' in content:
    content = content.replace(
        'from fastapi import',
        'from fastapi import'
    )
    # Add CORS import after FastAPI imports
    content = content.replace(
        'from fastapi.responses import JSONResponse',
        'from fastapi.responses import JSONResponse\nfrom fastapi.middleware.cors import CORSMiddleware'
    )

# Add CORS middleware after app creation
app_pattern = r'app = FastAPI\([^)]+\)'
match = re.search(app_pattern, content)
if match:
    insert_pos = match.end()
    cors_code = '''

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)'''
    content = content[:insert_pos] + cors_code + content[insert_pos:]

# Write back
with open(sys.argv[1], 'w') as f:
    f.write(content)

print("CORS added successfully")
EOF

# Apply patches
python /tmp/cors_patch.py memory_service/api.py
python /tmp/cors_patch.py plugin_manager/main.py
python /tmp/cors_patch.py goal_scheduler/main.py

echo "Done! CORS middleware added to all services."
echo "Please restart the services with: make all-down && make all-up"
