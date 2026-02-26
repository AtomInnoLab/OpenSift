# Solr Adapter

Connects to Apache Solr v8+ using the JSON Request API over HTTP. No extra dependencies beyond `httpx` are required.

## Configuration

```yaml
search:
  adapters:
    solr:
      enabled: true
      hosts: ["http://localhost:8983/solr"]
      index_pattern: "my_collection"
      username: "solr"           # optional
      password: "SolrRocks"      # optional
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `hosts` | `list[str]` | `["http://localhost:8983/solr"]` | Solr base URL |
| `index_pattern` | `str` | `"documents"` | Collection/core name |
| `username` | `str` | `None` | Basic auth username |
| `password` | `str` | `None` | Basic auth password |
| `timeout` | `float` | `30.0` | HTTP request timeout (seconds) |

## Search Behavior

- Uses the `edismax` query parser
- Query fields: `title^2 content description`
- Highlighting via Solr's built-in highlighter
- Recency filtering via `fq` filter queries on `timestamp`

## Docker (for testing)

```bash
docker run -d --name solr \
  -p 8983:8983 \
  solr:9.7 solr-precreate documents
```
