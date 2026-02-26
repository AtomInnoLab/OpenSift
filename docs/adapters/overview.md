# Adapters Overview

OpenSift connects to search backends through the **adapter pattern**. Each adapter implements the `SearchAdapter` interface, providing a consistent API regardless of the underlying search engine.

## Built-in Adapters

| Adapter | Backend | Extra Dependency | Description |
|---------|---------|:----------------:|-------------|
| [AtomWalker](../adapters/elasticsearch.md) | AtomWalker ScholarSearch | — | Academic paper search with JCR/CCF metadata |
| [Elasticsearch](elasticsearch.md) | Elasticsearch v8+ | `pip install opensift[elasticsearch]` | BM25 full-text search + highlighting |
| [OpenSearch](opensearch.md) | OpenSearch v2+ | `pip install opensift[opensearch]` | AWS-compatible Elasticsearch fork |
| [Solr](solr.md) | Apache Solr v8+ | — (uses httpx) | edismax full-text search |
| [MeiliSearch](meilisearch.md) | MeiliSearch | — (uses httpx) | Instant, typo-tolerant search |
| [Wikipedia](wikipedia.md) | Wikipedia (all languages) | `wikipedia-api` | Encyclopedia article search |

## Adapter Interface

Every adapter must implement:

```python
class SearchAdapter(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    async def initialize(self) -> None: ...

    @abstractmethod
    async def shutdown(self) -> None: ...

    @abstractmethod
    async def search(self, query: str, options: SearchOptions) -> RawResults: ...

    @abstractmethod
    async def fetch_document(self, doc_id: str) -> dict[str, Any]: ...

    @abstractmethod
    def map_to_standard_schema(self, raw_result: dict[str, Any]) -> StandardDocument: ...

    @abstractmethod
    async def health_check(self) -> AdapterHealth: ...
```

## Configuration

Enable and configure adapters in `opensift-config.yaml`:

```yaml
search:
  default_adapter: meilisearch
  adapters:
    meilisearch:
      enabled: true
      hosts: ["http://localhost:7700"]
      index_pattern: "documents"
      api_key: "your-master-key"
    elasticsearch:
      enabled: true
      hosts: ["http://localhost:9200"]
      index_pattern: "docs-*"
```

## Multi-Adapter Search

When multiple adapters are enabled, specify which to use per request:

```json
{
  "query": "solar nowcasting",
  "options": {
    "adapters": ["elasticsearch", "wikipedia"]
  }
}
```

Each result includes a `source_adapter` field to identify its origin.

## Building a Custom Adapter

See [Custom Adapter](custom.md) for a step-by-step guide.
