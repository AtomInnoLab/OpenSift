# @opensift/client

TypeScript/JavaScript client for the [OpenSift](https://github.com/AtomInnoLab/OpenSift) API — AI-augmented search with query planning and result verification.

## Installation

```bash
npm install @opensift/client
```

## Quick Start

```typescript
import { OpenSiftClient } from "@opensift/client";

const client = new OpenSiftClient({
  baseUrl: "http://localhost:8080",
});

// Complete search — waits for all results
const response = await client.search("solar nowcasting deep learning");

console.log(`Found ${response.perfect_results.length} perfect results`);
for (const r of response.perfect_results) {
  console.log(`  [${r.classification}] ${r.result.title} (score: ${r.weighted_score})`);
}
```

## API Reference

### Constructor

```typescript
const client = new OpenSiftClient({
  baseUrl: "http://localhost:8080", // required
  timeout: 120_000,                // request timeout in ms (default: 2 minutes)
  headers: {                       // custom headers for every request
    Authorization: "Bearer ...",
  },
  fetch: customFetch,              // custom fetch implementation (optional)
});
```

### `client.search(query, options?)`

Execute an AI-enhanced search with query planning, verification, and classification.

```typescript
const result = await client.search("deep learning for drug discovery", {
  max_results: 20,
  verify: true,       // enable LLM verification (default: true)
  decompose: true,    // decompose query into sub-queries (default: true)
  classify: true,     // classify results as perfect/partial/reject (default: true)
  adapters: ["elasticsearch", "wikipedia"], // restrict to specific backends
});

// Classified results (when classify=true)
result.perfect_results;   // ScoredResult[] — fully match all criteria
result.partial_results;   // ScoredResult[] — partial matches
result.rejected_count;    // number of filtered-out results

// Raw results (when classify=false)
result.raw_results;       // RawVerifiedResult[] — unclassified
```

### `client.searchStream(query, options?)`

Streaming search via Server-Sent Events — results arrive as they're verified.

```typescript
for await (const event of client.searchStream("quantum computing applications")) {
  switch (event.event) {
    case "criteria":
      console.log("Planning complete:", event.data.criteria_result);
      break;
    case "search_complete":
      console.log(`Search found ${event.data.total_results} results`);
      break;
    case "result":
      console.log("Verified result:", event.data.scored_result);
      break;
    case "done":
      console.log(`Done in ${event.data.processing_time_ms}ms`);
      break;
    case "error":
      console.error("Error:", event.data.error);
      break;
  }
}
```

### `client.plan(query, options?)`

Generate search queries and screening criteria without executing search.

```typescript
const plan = await client.plan("CRISPR gene editing clinical trials");

console.log("Search queries:", plan.criteria_result.search_queries);
for (const c of plan.criteria_result.criteria) {
  console.log(`  [${c.type}] ${c.name} (weight: ${c.weight})`);
}
```

### `client.batchSearch(queries, options?)`

Execute multiple queries in a single request.

```typescript
const batch = await client.batchSearch(
  ["solar energy storage", "wind turbine optimization", "nuclear fusion progress"],
  { max_results: 5, export_format: "csv" },
);

console.log(`Processed ${batch.total_queries} queries in ${batch.processing_time_ms}ms`);
for (const result of batch.results) {
  console.log(`  "${result.query}": ${result.perfect_results.length} perfect results`);
}
```

### `client.health()` / `client.adapterHealth()`

```typescript
const health = await client.health();
console.log(`Server v${health.version}: ${health.active_adapters.join(", ")}`);

const adapters = await client.adapterHealth();
for (const [name, status] of Object.entries(adapters.adapters)) {
  console.log(`  ${name}: ${status.status} (${status.latency_ms}ms)`);
}
```

## Error Handling

```typescript
import {
  OpenSiftAPIError,
  OpenSiftValidationError,
  OpenSiftTimeoutError,
  OpenSiftConnectionError,
} from "@opensift/client";

try {
  await client.search("test query");
} catch (error) {
  if (error instanceof OpenSiftValidationError) {
    // 422 — invalid request parameters
    console.error("Validation error:", error.body);
  } else if (error instanceof OpenSiftAPIError) {
    // Other HTTP errors (500, etc.)
    console.error(`API error (${error.status}):`, error.body);
  } else if (error instanceof OpenSiftTimeoutError) {
    // Request exceeded timeout
    console.error("Request timed out");
  } else if (error instanceof OpenSiftConnectionError) {
    // Network / DNS / connection refused
    console.error("Connection failed:", error.message);
  }
}
```

## Requirements

- Node.js >= 18 (uses native `fetch` and `ReadableStream`)
- TypeScript >= 5.0 (for type definitions)

## License

Apache-2.0
