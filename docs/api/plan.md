# Plan API

The `/v1/plan` endpoint exposes the Query Planner as an independent capability — generate search queries and screening criteria without running search or verification.

## Endpoint

```
POST /v1/plan
```

## Request

```bash
curl -X POST http://localhost:8080/v1/plan \
  -H "Content-Type: application/json" \
  -d '{ "query": "Deep learning papers on solar nowcasting" }'
```

## Response

```json
{
  "request_id": "plan_a1b2c3d4e5f6",
  "query": "Deep learning papers on solar nowcasting",
  "criteria_result": {
    "search_queries": [
      "\"solar nowcasting\" deep learning",
      "solar irradiance forecasting neural network"
    ],
    "criteria": [
      {
        "criterion_id": "c1",
        "type": "task",
        "name": "Solar nowcasting research",
        "description": "The paper must address solar irradiance nowcasting",
        "weight": 0.6
      },
      {
        "criterion_id": "c2",
        "type": "method",
        "name": "Deep learning methods",
        "description": "The paper must use deep learning or neural network methods",
        "weight": 0.4
      }
    ]
  },
  "processing_time_ms": 850
}
```

## Use Cases

- **Debug planner output** — Inspect generated queries and criteria before running the full pipeline
- **External search pipeline** — Feed the generated queries into your own search system
- **Batch pre-computation** — Pre-compute criteria for incremental or scheduled workflows
