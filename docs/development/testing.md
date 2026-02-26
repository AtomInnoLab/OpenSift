# Testing

OpenSift has two test layers: **unit tests** (fast, mocked) and **integration tests** (Docker-based, real backends).

## Unit Tests

```bash
make test-unit
```

Unit tests mock all external dependencies and run instantly.

## Integration Tests

Integration tests run each adapter against a real search backend via Docker containers with seeded mock data.

### Test a Single Adapter

Each adapter can be tested independently — only the required Docker container is started:

```bash
make test-es          # Elasticsearch
make test-opensearch  # OpenSearch
make test-solr        # Solr
make test-meili       # MeiliSearch
make test-wikipedia   # Wikipedia (no Docker needed)
```

Or use the generic form:

```bash
make test-adapter ADAPTER=elasticsearch
```

### Test All Adapters

```bash
make test-backends-up    # Start all 4 Docker backends
make test-integration    # Run all integration tests
make test-backends-down  # Stop and remove containers
```

### Using pytest markers directly

```bash
# Single adapter
pytest tests/integration/ -m elasticsearch

# Multiple adapters
pytest tests/integration/ -m "solr or meilisearch"
```

### Docker Services

| Adapter | Docker Image | Port | Marker |
|---------|-------------|:----:|--------|
| Elasticsearch | `elasticsearch:8.17.0` | 9200 | `elasticsearch` |
| OpenSearch | `opensearch:2.18.0` | 9201 | `opensearch` |
| Solr | `solr:9.7` | 8983 | `solr` |
| MeiliSearch | `meilisearch:v1.12` | 7700 | `meilisearch` |
| Wikipedia | *(live API)* | — | `wikipedia` |

### What's Tested

Each adapter's integration tests cover:

- **Health check** — Adapter reports healthy status
- **Search** — Returns relevant results for known queries
- **Relevance** — Correct documents rank high for specific terms
- **Empty results** — Gibberish queries return zero results
- **Result limits** — `max_results` is respected
- **Document fetch** — Individual documents retrieved by ID
- **Not found** — Proper error for nonexistent documents
- **Schema mapping** — Raw results map to `StandardDocument`
- **Search + normalize** — End-to-end search and mapping
