# Elasticsearch Adapter

Connects to Elasticsearch v8+ clusters for full-text search with BM25, highlighting, and recency filtering.

## Installation

```bash
pip install opensift[elasticsearch]
```

## Configuration

```yaml
search:
  adapters:
    elasticsearch:
      enabled: true
      hosts: ["http://localhost:9200"]
      index_pattern: "documents"
      username: "elastic"        # optional
      password: "changeme"       # optional
      api_key: "your-api-key"    # optional (alternative to username/password)
      verify_certs: true
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `hosts` | `list[str]` | `["http://localhost:9200"]` | Elasticsearch node URLs |
| `index_pattern` | `str` | `"*"` | Index pattern for searches |
| `username` | `str` | `None` | Basic auth username |
| `password` | `str` | `None` | Basic auth password |
| `api_key` | `str` | `None` | API key authentication |
| `verify_certs` | `bool` | `true` | Verify TLS certificates |

## Search Behavior

- Uses `multi_match` with `best_fields` across `title`, `content`, `description`
- Title is boosted 2x in the query (not in mapping)
- Fuzziness set to `AUTO` for typo tolerance
- Highlights returned for `title` and `content`

## Health Check

Reports Elasticsearch cluster health:

- **green** → `healthy`
- **yellow** → `degraded`
- **red** → `unhealthy`

## Docker (for testing)

```bash
docker run -d --name es \
  -p 9200:9200 \
  -e "discovery.type=single-node" \
  -e "xpack.security.enabled=false" \
  docker.elastic.co/elasticsearch/elasticsearch:8.17.0
```
