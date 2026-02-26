# Health API

Health check endpoints for monitoring OpenSift and its adapters.

## Server Health

```
GET /v1/health
```

```bash
curl http://localhost:8080/v1/health
```

```json
{
  "status": "healthy",
  "version": "0.1.0",
  "uptime_seconds": 3600
}
```

## Adapter Health

```
GET /v1/health/adapters
```

Returns the health status of each configured search adapter:

```bash
curl http://localhost:8080/v1/health/adapters
```

```json
{
  "adapters": {
    "elasticsearch": {
      "status": "healthy",
      "latency_ms": 12,
      "message": "Cluster: opensift, Nodes: 1"
    },
    "wikipedia": {
      "status": "healthy",
      "latency_ms": 85,
      "message": "Wikipedia API (en)"
    }
  }
}
```

| Status | Meaning |
|--------|---------|
| `healthy` | Adapter is fully operational |
| `degraded` | Adapter is working but with issues (e.g. yellow cluster) |
| `unhealthy` | Adapter is not reachable |
