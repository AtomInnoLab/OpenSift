# Search API

The `/v1/search` endpoint is the primary interface to the OpenSift pipeline.

## Endpoint

```
POST /v1/search
```

## Request Body

```json
{
  "query": "Deep learning papers on solar nowcasting",
  "options": {
    "max_results": 10,
    "verify": true,
    "classify": true,
    "stream": false,
    "adapters": ["wikipedia"]
  }
}
```

| Field | Type | Required | Default | Description |
|-------|------|:--------:|---------|-------------|
| `query` | `string` | Yes | — | Natural language search query |
| `options.max_results` | `int` | No | `20` | Maximum results to retrieve |
| `options.verify` | `bool` | No | `true` | Run LLM verification on results |
| `options.classify` | `bool` | No | `true` | Classify results into perfect/partial/reject |
| `options.stream` | `bool` | No | `false` | Enable SSE streaming output |
| `options.adapters` | `string[]` | No | config default | Which adapters to search |

## Output Modes

### Complete Mode (default)

Returns all results after the full pipeline completes.

**Request:**

```bash
curl -X POST http://localhost:8080/v1/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Deep learning papers on solar nowcasting",
    "options": { "max_results": 10, "verify": true }
  }'
```

**Response:**

```json
{
  "request_id": "req_a1b2c3d4e5f6",
  "status": "completed",
  "processing_time_ms": 3200,
  "criteria_result": {
    "search_queries": ["\"solar nowcasting\" deep learning", "solar irradiance forecasting neural network"],
    "criteria": [
      {
        "criterion_id": "c1",
        "type": "task",
        "name": "Solar nowcasting research",
        "description": "The paper must address solar irradiance nowcasting",
        "weight": 0.6
      }
    ]
  },
  "perfect_results": [ ... ],
  "partial_results": [ ... ],
  "rejected_results": [ ... ],
  "rejected_count": 5,
  "total_scanned": 20
}
```

### Streaming Mode (SSE)

Set `"stream": true` to receive results via Server-Sent Events as each result is verified.

```
Pipeline:  criteria → search_complete → result × N → done (or error)
```

**Request:**

```bash
curl -N -X POST http://localhost:8080/v1/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Deep learning papers on solar nowcasting",
    "options": { "max_results": 10, "stream": true }
  }'
```

**SSE Event Types:**

| Event | Count | Description |
|-------|:-----:|-------------|
| `criteria` | 1 | Planning complete — search queries + screening criteria |
| `search_complete` | 1 | Search finished — raw results before verification |
| `result` | N | One result verified — with classification and score |
| `done` | 1 | All processing complete — summary statistics |
| `error` | 0–1 | Unrecoverable error |

## Options

### Skip Classification

Set `"classify": false` to get raw verification assessments without perfect/partial/reject labels:

```bash
curl -X POST http://localhost:8080/v1/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "solar nowcasting",
    "options": { "classify": false }
  }'
```

### Skip Verification

Set `"verify": false` to use OpenSift as a pure search proxy (no LLM verification):

```bash
curl -X POST http://localhost:8080/v1/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "RAG retrieval augmented generation",
    "options": { "verify": false, "max_results": 20 }
  }'
```
