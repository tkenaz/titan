#!/bin/bash
# Test Model Gateway endpoints

set -e

BASE_URL="http://localhost:8081"
TOKEN="${ADMIN_TOKEN:-titan-secret-token-change-me-in-production}"

echo "Testing Model Gateway..."
echo "========================"

# Health check
echo -n "1. Health check... "
if curl -s ${BASE_URL}/health | jq -r '.status' | grep -q "healthy"; then
    echo "✓ OK"
else
    echo "✗ FAIL"
    exit 1
fi

# List models
echo -n "2. List models... "
MODELS=$(curl -s ${BASE_URL}/models)
if echo "$MODELS" | jq -r '.models[0].name' > /dev/null 2>&1; then
    echo "✓ OK"
    echo "   Available models:"
    echo "$MODELS" | jq -r '.models[] | "   - \(.name): $\(.input_cost)/token in, $\(.output_cost)/token out"'
else
    echo "✗ FAIL"
    exit 1
fi

# Budget stats
echo -n "3. Budget stats... "
BUDGET=$(curl -s -H "Authorization: Bearer ${TOKEN}" ${BASE_URL}/budget/stats)
if echo "$BUDGET" | jq -r '.daily_limit_usd' > /dev/null 2>&1; then
    echo "✓ OK"
    LIMIT=$(echo "$BUDGET" | jq -r '.daily_limit_usd')
    SPENT=$(echo "$BUDGET" | jq -r '.daily_spent_usd')
    REMAINING=$(echo "$BUDGET" | jq -r '.remaining_usd')
    echo "   Daily limit: \${LIMIT}"
    echo "   Spent today: \${SPENT}"
    echo "   Remaining: \${REMAINING}"
else
    echo "✗ FAIL"
    echo "$BUDGET"
fi

# Non-streaming completion
echo -n "4. Non-streaming completion... "
RESPONSE=$(curl -s -X POST ${BASE_URL}/proxy/gpt-4o \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "Say hello in exactly 5 words"}],
    "temperature": 0.7,
    "stream": false
  }')

if echo "$RESPONSE" | jq -r '.choices[0].message.content' > /dev/null 2>&1; then
    echo "✓ OK"
    echo "   Response: $(echo "$RESPONSE" | jq -r '.choices[0].message.content')"
    echo "   Tokens: $(echo "$RESPONSE" | jq -r '.usage.total_tokens')"
    COST=$(echo "$RESPONSE" | jq -r '.cost.total_cost')
    echo "   Cost: \${COST}"
    
    # Check signature
    if echo "$RESPONSE" | jq -r '.signature' > /dev/null 2>&1; then
        echo "   Signature: $(echo "$RESPONSE" | jq -r '.signature' | cut -c1-16)..."
    fi
else
    echo "✗ FAIL"
    echo "$RESPONSE" | jq .
fi

# Insights stats (if available)
echo -n "5. Insights stats... "
INSIGHTS=$(curl -s -H "Authorization: Bearer ${TOKEN}" ${BASE_URL}/insights/stats?hours=1)
if echo "$INSIGHTS" | jq . > /dev/null 2>&1; then
    if [ "$(echo "$INSIGHTS" | jq -r '.detail')" = "Insights not available" ]; then
        echo "✓ OK (insights not configured)"
    else
        echo "✓ OK"
        echo "$INSIGHTS" | jq .
    fi
else
    echo "✗ FAIL"
fi

# Streaming test
echo -n "6. Streaming completion... "
STREAM_FILE=$(mktemp)
HTTP_CODE=$(curl -s -o $STREAM_FILE -w "%{http_code}" -X POST ${BASE_URL}/proxy/gpt-4o \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "Count from 1 to 3"}],
    "stream": true
  }')

if [ "$HTTP_CODE" = "200" ] && grep -q "data:" $STREAM_FILE; then
    echo "✓ OK"
    echo "   Chunks received: $(grep -c "data:" $STREAM_FILE)"
    # Show first chunk
    echo "   First chunk: $(grep "data:" $STREAM_FILE | head -1)"
else
    echo "✗ FAIL (HTTP $HTTP_CODE)"
    cat $STREAM_FILE
fi
rm -f $STREAM_FILE

echo "========================"
echo "Model Gateway tests complete!"
