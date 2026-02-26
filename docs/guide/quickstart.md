# Quick Start

Get OpenSift running in under 5 minutes.

## Requirements

- Python 3.11+
- [Poetry](https://python-poetry.org/) 2.0+

## Installation

```bash
git clone https://github.com/AtomInnoLab/OpenSift.git
cd opensift

# Development environment (recommended)
make dev-setup

# Or directly with Poetry
poetry install
```

### Optional adapter dependencies

```bash
# Elasticsearch support
pip install opensift[elasticsearch]

# OpenSearch support
pip install opensift[opensearch]

# All optional adapters
pip install opensift[all]
```

## Configuration

```bash
cp opensift-config.example.yaml opensift-config.yaml
cp .env.example .env
```

Edit `.env` to set your WisModel API key:

```dotenv
OPENSIFT_AI__API_KEY=your-wismodel-key
```

Configure your search backend (default is AtomWalker academic search):

```dotenv
OPENSIFT_SEARCH__ADAPTERS__ATOMWALKER__API_KEY=wsk_xxxxx
```

!!! tip "WisModel API Key"
    WisModel is available via the [WisPaper API Hub](https://wispaper.ai). Contact the team to obtain your API key.

## Start the Server

=== "Development"

    ```bash
    make run
    # or: poetry run opensift --reload --log-level debug
    ```

=== "Production"

    ```bash
    make run-prod
    # or: poetry run opensift --workers 4 --log-level info
    ```

The server starts at:

| Endpoint | URL |
|----------|-----|
| API | `http://localhost:8080` |
| Docs (Swagger) | `http://localhost:8080/docs` |
| Debug Panel | `http://localhost:8080/debug` |

## Your First Search

```bash
curl -X POST http://localhost:8080/v1/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Deep learning papers on solar nowcasting",
    "options": {
      "max_results": 10,
      "verify": true
    }
  }'
```

The response contains:

- `criteria_result` — the generated search queries and screening criteria
- `perfect_results` — results that fully match all criteria
- `partial_results` — results that partially match
- `rejected_results` — filtered out results

## Next Steps

- [API Reference](../api/search.md) — Full API documentation with all options
- [Python SDK](../sdk.md) — Use OpenSift from Python code
- [Adapters](../adapters/overview.md) — Connect your own search backend
- [Configuration](configuration.md) — All configuration options
