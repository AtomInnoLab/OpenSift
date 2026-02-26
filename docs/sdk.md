# Python SDK

OpenSift ships with a Python client library supporting both sync and async modes.

## Installation

The SDK is included with OpenSift:

```bash
pip install opensift
```

## Sync Client

```python
from opensift.client import OpenSiftClient

client = OpenSiftClient("http://localhost:8080")
```

### Plan (Query Planning Only)

```python
plan = client.plan("solar nowcasting deep learning")
print(plan["criteria_result"]["search_queries"])
print(plan["criteria_result"]["criteria"])
```

### Search (Complete Mode)

```python
response = client.search("solar nowcasting deep learning")

for r in response["perfect_results"]:
    print(f"[{r['result']['source_adapter']}] {r['result']['title']}")
    print(f"  Score: {r['weighted_score']}")
    print(f"  Classification: {r['classification']}")
```

### Search (Streaming Mode)

```python
for event in client.search_stream("solar nowcasting deep learning"):
    evt = event["event"]
    data = event["data"]

    if evt == "criteria":
        print(f"Queries: {data['criteria_result']['search_queries']}")
    elif evt == "search_complete":
        print(f"Found {data['total_results']} results")
    elif evt == "result":
        r = data["scored_result"]
        print(f"  [{r['classification']}] {r['result']['title']}")
    elif evt == "done":
        print(f"Done: {data['perfect_count']}P / {data['partial_count']}A / {data['rejected_count']}R")
```

### Batch Search

```python
batch = client.batch_search(
    ["solar nowcasting", "wind power forecasting", "battery degradation"],
    max_results=5,
    export_format="csv",
)
print(batch["export_data"])  # CSV text
```

## Async Client

```python
from opensift.client import AsyncOpenSiftClient

async with AsyncOpenSiftClient("http://localhost:8080") as client:
    # Planning
    plan = await client.plan("solar nowcasting")
    print(plan["criteria_result"])

    # Complete search
    response = await client.search("solar nowcasting")

    # Streaming
    async for event in client.search_stream("solar nowcasting"):
        if event["event"] == "result":
            r = event["data"]["scored_result"]
            print(f"[{r['result']['source_adapter']}] {r['result']['title']}")
```

## Client Options

Both clients accept the same constructor parameters:

```python
client = OpenSiftClient(
    base_url="http://localhost:8080",
    timeout=60.0,    # Request timeout in seconds
)
```
