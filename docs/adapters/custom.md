# Custom Adapter

Build your own adapter to connect OpenSift with any search backend.

## Step 1: Implement the Interface

Create a new module under `src/opensift/adapters/`:

```python
from opensift.adapters.base.adapter import AdapterHealth, RawResults, SearchAdapter
from opensift.models.document import DocumentMetadata, StandardDocument
from opensift.models.query import SearchOptions


class MyAdapter(SearchAdapter):
    def __init__(self, base_url: str = "http://localhost:9999", **kwargs):
        self._base_url = base_url
        self._client = None

    @property
    def name(self) -> str:
        return "my-backend"

    async def initialize(self) -> None:
        """Create HTTP client, verify connection."""
        import httpx
        self._client = httpx.AsyncClient(base_url=self._base_url)

    async def shutdown(self) -> None:
        """Close connections."""
        if self._client:
            await self._client.aclose()

    async def search(self, query: str, options: SearchOptions) -> RawResults:
        """Execute search and return raw results."""
        resp = await self._client.get("/search", params={"q": query, "limit": options.max_results})
        data = resp.json()
        return RawResults(
            total_hits=data["total"],
            documents=data["results"],
            took_ms=data.get("took_ms", 0),
        )

    async def fetch_document(self, doc_id: str) -> dict:
        """Retrieve a single document by ID."""
        resp = await self._client.get(f"/docs/{doc_id}")
        return resp.json()

    def map_to_standard_schema(self, raw_result: dict) -> StandardDocument:
        """Map raw result to OpenSift's standard format."""
        return StandardDocument(
            id=raw_result.get("id", ""),
            title=raw_result.get("name", "Untitled"),
            content=raw_result.get("body", ""),
            score=raw_result.get("relevance", 0.0),
            metadata=DocumentMetadata(
                source=self.name,
                url=raw_result.get("link"),
            ),
        )

    async def health_check(self) -> AdapterHealth:
        """Check backend health."""
        try:
            resp = await self._client.get("/health")
            return AdapterHealth(status="healthy" if resp.status_code == 200 else "unhealthy")
        except Exception as e:
            return AdapterHealth(status="unhealthy", message=str(e))
```

## Step 2: Register the Adapter

Add your adapter to `src/opensift/adapters/__init__.py`:

```python
from opensift.adapters.my_backend.adapter import MyAdapter
```

## Step 3: Configure

```yaml
search:
  default_adapter: my-backend
  adapters:
    my-backend:
      enabled: true
      hosts: ["http://localhost:9999"]
```

## Key Points

- **`search()`** should return `RawResults` with a list of raw dicts
- **`map_to_standard_schema()`** normalizes each raw dict to `StandardDocument`
- **`health_check()`** should be non-throwing — return `AdapterHealth` with status
- Use `async` for all I/O operations
