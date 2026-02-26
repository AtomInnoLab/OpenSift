# Wikipedia Adapter

Searches Wikipedia articles across all languages using the `wikipedia-api` library. No Docker setup needed.

## Installation

```bash
pip install wikipedia-api
```

## Configuration

```yaml
search:
  adapters:
    wikipedia:
      enabled: true
```

The language can be set programmatically (defaults to `en`).

## Search Behavior

- Uses the Wikipedia search API to find matching articles
- Retrieves full article summaries as content
- Returns article URLs for each result
- Supports all Wikipedia languages

## Use Cases

- Quick prototyping without setting up a search backend
- Enriching results with encyclopedia knowledge
- Multi-language search scenarios
