# OpenSift SDKs

Multi-language client libraries for the [OpenSift](https://github.com/AtomInnoLab/OpenSift) API.

## Available SDKs

| Language   | Package                  | Status       | Directory      |
| ---------- | ------------------------ | ------------ | -------------- |
| Python     | `opensift` (PyPI)        | ✅ Stable     | `python/`      |
| TypeScript | `@opensift/client` (npm) | 🚧 Planned   | `typescript/`  |
| Go         | `opensift-go`            | 🚧 Planned   | `go/`          |
| Java       | `opensift-java` (Maven)  | 📋 Roadmap   | `java/`        |
| Rust       | `opensift` (crates.io)   | 📋 Roadmap   | `rust/`        |

## Architecture

All SDKs are generated from and validated against the OpenSift **OpenAPI specification** (`/openapi.json`).

```
┌──────────────────────────────────────────────────────────┐
│                  OpenSift Server                         │
│                                                          │
│   FastAPI  ──►  /openapi.json  (auto-generated spec)     │
└──────────────────────┬───────────────────────────────────┘
                       │
              ┌────────▼────────┐
              │  OpenAPI Spec   │
              │  (openapi.json) │
              └────────┬────────┘
                       │
        ┌──────────────┼──────────────────┐
        │              │                  │
   ┌────▼────┐   ┌─────▼─────┐    ┌──────▼──────┐
   │ Python  │   │TypeScript │    │  Go / Java  │
   │  SDK    │   │   SDK     │    │  / Rust SDK │
   │(manual) │   │(generated)│    │ (generated) │
   └─────────┘   └───────────┘    └─────────────┘
```

### SDK Generation Strategy

- **Python SDK**: Hand-written (lives in `src/opensift/client/`), published to PyPI
- **TypeScript SDK**: Hand-written core with types from OpenAPI spec
- **Go / Java / Rust**: Auto-generated via [OpenAPI Generator](https://openapi-generator.tech/), then hand-tuned

### Shared Contract

All SDKs must implement these core operations:

| Method           | HTTP Endpoint       | Description                        |
| ---------------- | ------------------- | ---------------------------------- |
| `health()`       | `GET /v1/health`    | Server health check                |
| `plan()`         | `POST /v1/plan`     | Query planning (plan only)         |
| `search()`       | `POST /v1/search`   | Complete search (wait for all)     |
| `searchStream()` | `POST /v1/search`   | Streaming search (SSE)             |
| `batchSearch()`  | `POST /v1/search/batch` | Batch search (multiple queries)|

## Development

### Export OpenAPI Spec

```bash
# Start the server and download the spec
make run &
curl http://localhost:8080/openapi.json -o sdks/openapi.json

# Or generate without starting the server
python -c "
from opensift.api.app import create_app
import json
app = create_app()
print(json.dumps(app.openapi(), indent=2))
" > sdks/openapi.json
```

### Generate SDKs

```bash
# TypeScript
npx @openapitools/openapi-generator-cli generate \
  -i sdks/openapi.json \
  -g typescript-fetch \
  -o sdks/typescript/src/generated

# Go
openapi-generator generate \
  -i sdks/openapi.json \
  -g go \
  -o sdks/go/

# Java
openapi-generator generate \
  -i sdks/openapi.json \
  -g java \
  -o sdks/java/ \
  --additional-properties=library=native
```
