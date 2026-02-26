# Configuration

OpenSift supports three layers of configuration (highest to lowest priority):

1. **Environment variables** — `OPENSIFT_` prefix, nesting with `__`
2. **YAML file** — `opensift-config.yaml`
3. **Defaults**

## Key Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENSIFT_AI__API_KEY` | WisModel API Key | — |
| `OPENSIFT_AI__BASE_URL` | WisModel API endpoint | WisPaper API Hub |
| `OPENSIFT_AI__MODEL_PLANNER` | WisModel version for planning | `WisModel-20251110` |
| `OPENSIFT_AI__MODEL_VERIFIER` | WisModel version for verification | `WisModel-20251110` |
| `OPENSIFT_SEARCH__DEFAULT_ADAPTER` | Default search backend | `atomwalker` |

## YAML Configuration

The full configuration file (`opensift-config.yaml`):

```yaml
# ─── AI (WisModel) ───────────────────────────────────────
ai:
  api_key: "your-wismodel-key"
  base_url: "https://api.wispaper.ai/v1"
  model_planner: "WisModel-20251110"
  model_verifier: "WisModel-20251110"

# ─── Search ──────────────────────────────────────────────
search:
  default_adapter: atomwalker
  max_results: 20
  adapters:
    atomwalker:
      enabled: true
      api_key: "wsk_xxxxx"
    elasticsearch:
      enabled: false
      hosts: ["http://localhost:9200"]
      index_pattern: "documents"
    meilisearch:
      enabled: false
      hosts: ["http://localhost:7700"]
      index_pattern: "documents"
      api_key: "your-master-key"

# ─── Server ─────────────────────────────────────────────
server:
  host: "0.0.0.0"
  port: 8080
  workers: 1

# ─── Observability ──────────────────────────────────────
observability:
  log_level: info
  log_format: json
```

## Adapter Configuration

Each adapter can be configured under `search.adapters.<name>`:

```yaml
search:
  adapters:
    elasticsearch:
      enabled: true
      hosts: ["http://localhost:9200"]
      index_pattern: "my-index-*"
      username: "elastic"
      password: "changeme"
    solr:
      enabled: true
      hosts: ["http://localhost:8983/solr"]
      index_pattern: "my_collection"
    wikipedia:
      enabled: true
```

See the [Adapters Overview](../adapters/overview.md) for adapter-specific options.

## Docker Configuration

Environment variables work seamlessly with Docker:

```yaml
# docker-compose.yml
services:
  opensift:
    image: opensift/core:latest
    environment:
      - OPENSIFT_AI__API_KEY=your-key
      - OPENSIFT_SEARCH__DEFAULT_ADAPTER=elasticsearch
      - OPENSIFT_SEARCH__ADAPTERS__ELASTICSEARCH__HOSTS=["http://es:9200"]
```
