# OpenSearch Adapter

Connects to OpenSearch v2+ — the AWS-maintained fork of Elasticsearch with a compatible query DSL.

## Installation

```bash
pip install opensift[opensearch]
```

## Configuration

```yaml
search:
  adapters:
    opensearch:
      enabled: true
      hosts: ["https://localhost:9200"]
      index_pattern: "documents"
      username: "admin"
      password: "admin"
      verify_certs: false
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `hosts` | `list[str]` | `["https://localhost:9200"]` | OpenSearch node URLs |
| `index_pattern` | `str` | `"*"` | Index pattern for searches |
| `username` | `str` | `None` | HTTP basic-auth username |
| `password` | `str` | `None` | HTTP basic-auth password |
| `verify_certs` | `bool` | `true` | Verify TLS certificates |

## Search Behavior

The query DSL is largely compatible with Elasticsearch. The adapter uses:

- `multi_match` with `best_fields` across `title`, `content`, `description`
- Highlighting for `title` and `content`
- Recency filtering via range queries on `@timestamp`

## Docker (for testing)

```bash
docker run -d --name opensearch \
  -p 9200:9200 \
  -e "discovery.type=single-node" \
  -e "plugins.security.disabled=true" \
  -e "OPENSEARCH_INITIAL_ADMIN_PASSWORD=YourPassword123!" \
  opensearchproject/opensearch:2.18.0
```
