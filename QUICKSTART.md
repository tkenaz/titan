# 🚀 Titan Quick Start

## TL;DR - Just Run This:

```bash
# 1. Make scripts executable (one time only)
chmod +x start_services.sh stop_services.sh diagnose.sh

# 2. Start everything
./start_services.sh

# 3. Run diagnostics to ensure everything is ready
./diagnose.sh

# 4. Run tests
python test_circuit_breaker_v2.py

# 5. When done, stop everything
./stop_services.sh
```

## If Something Goes Wrong:

### "Redis: Not ready" but services work
This is OK! Services use Docker networking (host.docker.internal), not localhost.

### "404 Not Found" errors
Services not running. Run `./start_services.sh`

### "Connection refused" errors  
Wait 15-20 seconds after starting services.

### Check what's running:
```bash
./diagnose.sh
# or
docker ps | grep titan
```

### View logs:
```bash
docker logs titan-memory-service
docker logs titan-plugin-manager
```

### Nuclear option (reset everything):
```bash
./stop_services.sh
docker system prune -a  # WARNING: Removes ALL Docker data
./start_services.sh
```

## Environment Variables

Create `.env` file:
```bash
ADMIN_TOKEN=titan-secret-token-change-me-in-production
OPENAI_API_KEY=sk-...  # Your OpenAI key
```

## Expected Test Output:

✅ Circuit Breaker Test:
- Plugin executes normally
- After 5 failures → DISABLED
- Manual reset → ACTIVE
- Container watchdog cleans up

✅ API Authentication Test:
- No token → 401 Unauthorized
- Wrong token → 401 Unauthorized  
- Correct token → 200 OK with stats
- Health endpoint → 200 OK (no auth)
