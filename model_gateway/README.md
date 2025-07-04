# Model Gateway

Unified LLM routing service with cost tracking and budget management for Titan.

## Features

- **Unified API**: Single endpoint `/proxy/{model}` for all LLM providers
- **Cost Tracking**: Real-time token usage and cost calculation
- **Budget Management**: Daily limits with hard stop capability
- **Event Logging**: All requests logged to Redis streams
- **HMAC Security**: Response signatures for stream integrity
- **OpenAI Compatible**: Drop-in replacement for OpenAI API
- **Multi-Provider**: Support for OpenAI, Azure, Google, Anthropic (extensible)

## Quick Start

1. **Configure models** in `config/models.yaml`:
```yaml
models:
  gpt-4o:
    provider: openai
    engine: gpt-4o
    input_cost: 0.0000025   # USD per token
    output_cost: 0.00001
    max_tokens: 8192
```

2. **Set environment variables**:
```bash
export OPENAI_API_KEY=sk-...
export ADMIN_TOKEN=your-secure-token
export HMAC_SECRET=your-hmac-secret
```

3. **Start the service**:
```bash
docker-compose -f docker-compose.model.yml up -d
```

## API Usage

### List Models
```bash
curl http://localhost:8081/models
```

### Make Completion Request
```bash
curl -X POST http://localhost:8081/proxy/gpt-4o \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "Hello"}],
    "temperature": 0.7,
    "stream": false
  }'
```

### Streaming Request
```bash
curl -X POST http://localhost:8081/proxy/gpt-4o \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "Tell me a story"}],
    "stream": true
  }'
```

### Check Budget Status
```bash
curl http://localhost:8081/budget/stats \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

### Reset Budget (Admin)
```bash
curl -X POST http://localhost:8081/budget/reset \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

## Configuration

### Model Configuration
Edit `config/models.yaml`:
- `provider`: LLM provider (openai, azure, etc.)
- `engine`: Actual model name for the provider
- `input_cost`: USD per input token
- `output_cost`: USD per output token
- `max_tokens`: Maximum tokens per request
- `timeout`: Request timeout in seconds

### Default Routing
Configure default models for different tasks:
```yaml
defaults:
  self_reflection: o3-pro
  vitals: gpt-4o
  experiment: o3-pro
```

### Budget Settings
```yaml
budget:
  daily_limit_usd: 20
  hard_stop: true          # Block requests when limit reached
  warning_threshold: 0.8   # Warn at 80% usage
```

## Events

All events are logged to Redis stream `agent.events`:

- `model.request.start`: Request initiated
- `model.request.complete`: Request completed with usage
- `model.budget.warning`: Budget threshold reached
- `model.budget.exceeded`: Budget limit exceeded
- `model.streaming.start`: Streaming response started

## Security

### HMAC Signatures
All responses include HMAC-SHA256 signatures:
- Non-streaming: `signature` field in response
- Streaming: `x_signature` in each chunk

Verify signatures client-side:
```python
import hmac
import hashlib

def verify_signature(data, signature, secret):
    expected = hmac.new(
        secret.encode('utf-8'),
        data.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)
```

## Monitoring

### Prometheus Metrics
Available at http://localhost:8081/metrics:
- `titan_model_requests_total{model}`: Total requests per model
- `titan_model_latency_seconds{model}`: Request latency histogram
- `titan_cost_usd_total`: Total cost in USD
- `titan_budget_exceeded_total`: Budget exceeded counter

### Real-time Monitoring
Connect to WebSocket for live events:
```javascript
const ws = new WebSocket('ws://localhost:8088/events');
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  if (data.event_type === 'model.request.complete') {
    console.log(`Model: ${data.model}, Cost: $${data.usd}`);
  }
};
```

## Extending Providers

Add new providers by implementing `ProviderInterface`:

```python
from model_gateway.providers import ProviderInterface

class AnthropicProvider(ProviderInterface):
    async def complete(self, messages, model, **kwargs):
        # Implementation
        pass
    
    async def stream(self, messages, model, **kwargs):
        # Implementation
        pass
    
    def count_tokens(self, text, model):
        # Implementation
        pass
```

Register in `ProviderFactory._providers`.

## Testing

```bash
# Run unit tests
pytest tests/test_model_gateway.py -v

# Test with curl
./scripts/test_model_gateway.sh
```

## Troubleshooting

### Budget Issues
- Check current spend: `GET /budget/stats`
- Reset if needed: `POST /budget/reset`
- Adjust limits in `config/models.yaml`

### Provider Errors
- Check API keys in environment
- Verify model names match provider's naming
- Check logs: `docker logs titan-model-gateway`

### Performance
- Monitor Redis memory usage
- Adjust stream `maxlen` if needed
- Use connection pooling for high load

## Insights & Analytics

Model Gateway stores detailed insights in PostgreSQL with PgVector:

### View Performance Stats
```bash
curl http://localhost:8081/insights/stats?hours=24 \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

### Get Cost Trends
```bash
curl http://localhost:8081/insights/trends?days=7 \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

### Find Similar Requests
```bash
curl "http://localhost:8081/insights/similar?query=explain%20kubernetes" \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

### Database Schema
- `model_insights`: Detailed request/response data
- `model_stats_hourly`: Hourly aggregated statistics  
- `model_cost_trends`: Daily cost trends and patterns

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│   Client    │────▶│ Model Gateway│────▶│  Providers  │
└─────────────┘     └──────┬───────┘     └─────────────┘
                           │                      │
                           ▼                      │
                    ┌─────────────┐               │
                    │    Redis    │               │
                    ├─────────────┤               │
                    │ Cost Track  │◀──────────────┘
                    │   Events    │
                    └─────────────┘
```

## License

Part of Titan project. See main LICENSE file.
