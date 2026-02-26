# MeiliSearch Adapter

Connects to MeiliSearch — a modern, developer-friendly search engine with instant, typo-tolerant search out of the box. No extra dependencies beyond `httpx` are required.

## Configuration

```yaml
search:
  adapters:
    meilisearch:
      enabled: true
      hosts: ["http://localhost:7700"]
      index_pattern: "documents"
      api_key: "your-master-key"
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `hosts` | `list[str]` | `["http://localhost:7700"]` | MeiliSearch instance URL |
| `index_pattern` | `str` | `"documents"` | Index UID |
| `api_key` | `str` | `None` | Master key or API key |
| `timeout` | `float` | `30.0` | HTTP request timeout (seconds) |

## Search Behavior

- Uses the `/indexes/{index}/search` REST endpoint
- Highlighting and cropping enabled by default
- Ranking score included via `showRankingScore`
- Recency filtering via numeric timestamp filters

## Features

- **Typo tolerance** — MeiliSearch handles typos automatically
- **Instant search** — Sub-50ms response times
- **No extra dependency** — Uses `httpx` (already a core OpenSift dependency)

## Docker (for testing)

```bash
docker run -d --name meili \
  -p 7700:7700 \
  -e MEILI_ENV=development \
  -e MEILI_MASTER_KEY=your-master-key \
  getmeili/meilisearch:v1.12
```
