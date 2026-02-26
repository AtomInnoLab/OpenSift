# Batch API

The `/v1/batch` endpoint processes multiple queries in a single request and supports CSV/JSON export.

## Endpoint

```
POST /v1/batch
```

## Request

```bash
curl -X POST http://localhost:8080/v1/batch \
  -H "Content-Type: application/json" \
  -d '{
    "queries": [
      "solar nowcasting deep learning",
      "wind power forecasting",
      "battery degradation prediction"
    ],
    "options": {
      "max_results": 5,
      "export_format": "csv"
    }
  }'
```

| Field | Type | Required | Default | Description |
|-------|------|:--------:|---------|-------------|
| `queries` | `string[]` | Yes | — | List of search queries |
| `options.max_results` | `int` | No | `20` | Results per query |
| `options.export_format` | `string` | No | `"json"` | Export format: `"json"` or `"csv"` |

## Response

```json
{
  "request_id": "batch_abc123",
  "status": "completed",
  "total_queries": 3,
  "results": [ ... ],
  "export_data": "query,title,classification,score\n...",
  "processing_time_ms": 12500
}
```

When `export_format` is `"csv"`, the `export_data` field contains the CSV text ready for download.
