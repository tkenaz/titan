#!/bin/bash
# Test CORS configuration for all services

set -e

echo "Testing CORS configuration..."
echo "============================="

# Test endpoints
SERVICES=(
    "Memory Service|http://localhost:8001/health"
    "Plugin Manager|http://localhost:8003/health"
    "Goal Scheduler|http://localhost:8004/health"
    "Model Gateway|http://localhost:8081/health"
)

# Browser origin
ORIGIN="http://localhost:5173"

echo "Testing preflight requests from origin: $ORIGIN"
echo

for service in "${SERVICES[@]}"; do
    IFS='|' read -r name url <<< "$service"
    
    echo -n "$name: "
    
    # Preflight request
    RESPONSE=$(curl -s -i -X OPTIONS "$url" \
        -H "Origin: $ORIGIN" \
        -H "Access-Control-Request-Method: GET" \
        -H "Access-Control-Request-Headers: authorization, content-type" \
        2>/dev/null | head -20)
    
    if echo "$RESPONSE" | grep -qi "access-control-allow-origin"; then
        echo "✓ CORS enabled"
        echo "$RESPONSE" | grep -i "access-control-" | sed 's/^/  /'
    else
        echo "✗ CORS not configured"
        # Check if service is running
        if curl -s "$url" > /dev/null 2>&1; then
            echo "  Service is running but CORS is not configured"
        else
            echo "  Service is not responding"
        fi
    fi
    echo
done

echo "============================="
echo "Testing authenticated endpoints with CORS..."
echo

# Test authenticated endpoint with CORS
TOKEN="${ADMIN_TOKEN:-titan-secret-token-change-me-in-production}"

echo -n "Memory Service /memory/stats: "
RESPONSE=$(curl -s -i -X OPTIONS "http://localhost:8001/memory/stats" \
    -H "Origin: $ORIGIN" \
    -H "Access-Control-Request-Method: GET" \
    -H "Access-Control-Request-Headers: authorization" \
    2>/dev/null | head -10)

if echo "$RESPONSE" | grep -qi "access-control-allow-origin"; then
    echo "✓ CORS preflight OK"
else
    echo "✗ CORS preflight failed"
fi

# Now test actual request with Authorization header
echo -n "Memory Service actual request: "
RESPONSE=$(curl -s -i "http://localhost:8001/memory/stats" \
    -H "Origin: $ORIGIN" \
    -H "Authorization: Bearer $TOKEN" \
    2>/dev/null | head -20)

if echo "$RESPONSE" | grep -qi "access-control-allow-origin"; then
    echo "✓ CORS headers present"
else
    echo "✗ CORS headers missing"
fi

echo
echo "============================="
echo "CORS test complete!"
