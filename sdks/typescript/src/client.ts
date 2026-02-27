/**
 * OpenSift TypeScript client — async client for the OpenSift REST API.
 *
 * @example
 * ```ts
 * import { OpenSiftClient } from "@opensift/client";
 *
 * const client = new OpenSiftClient({ baseUrl: "http://localhost:8080" });
 *
 * // Complete search
 * const result = await client.search("solar nowcasting deep learning");
 * console.log(result.perfect_results);
 *
 * // Streaming search
 * for await (const event of client.searchStream("solar nowcasting")) {
 *   console.log(event.event, event.data);
 * }
 * ```
 */

import {
  OpenSiftAPIError,
  OpenSiftConnectionError,
  OpenSiftTimeoutError,
  OpenSiftValidationError,
} from "./errors.js";
import type {
  AdapterHealthResponse,
  BatchSearchResponse,
  HealthResponse,
  OpenSiftClientOptions,
  PlanResponse,
  SearchResponse,
  StreamEvent,
} from "./types.js";

const DEFAULT_TIMEOUT = 120_000;

export class OpenSiftClient {
  private readonly baseUrl: string;
  private readonly timeout: number;
  private readonly headers: Record<string, string>;
  private readonly _fetch: typeof globalThis.fetch;

  constructor(options: OpenSiftClientOptions) {
    this.baseUrl = options.baseUrl.replace(/\/+$/, "");
    this.timeout = options.timeout ?? DEFAULT_TIMEOUT;
    this.headers = {
      "Content-Type": "application/json",
      ...options.headers,
    };
    this._fetch = options.fetch ?? globalThis.fetch;
  }

  // ── Health ───────────────────────────────────────────────────────────────

  /** Check server health. */
  async health(): Promise<HealthResponse> {
    return this.get<HealthResponse>("/v1/health");
  }

  /** Check per-adapter health status. */
  async adapterHealth(): Promise<AdapterHealthResponse> {
    return this.get<AdapterHealthResponse>("/v1/health/adapters");
  }

  // ── Plan ─────────────────────────────────────────────────────────────────

  /**
   * Generate search queries and screening criteria (plan only).
   * Does not execute search or verification.
   */
  async plan(
    query: string,
    options?: { decompose?: boolean },
  ): Promise<PlanResponse> {
    return this.post<PlanResponse>("/v1/plan", {
      query,
      options: { decompose: options?.decompose ?? true },
    });
  }

  // ── Search (complete mode) ───────────────────────────────────────────────

  /**
   * Execute an AI-enhanced search and wait for all results.
   *
   * @param query - Natural language search query
   * @param options - Search options
   * @returns Complete search response with classified results
   */
  async search(
    query: string,
    options?: {
      max_results?: number;
      verify?: boolean;
      decompose?: boolean;
      classify?: boolean;
      recency_filter?: string;
      adapters?: string[];
      timeout_seconds?: number;
    },
  ): Promise<SearchResponse> {
    return this.post<SearchResponse>("/v1/search", {
      query,
      options: {
        stream: false,
        ...options,
      },
    });
  }

  // ── Search (streaming mode) ──────────────────────────────────────────────

  /**
   * Execute an AI-enhanced search with streaming results via SSE.
   *
   * Yields events as results are verified:
   * - `criteria` — planning complete
   * - `search_complete` — search finished, raw results available
   * - `result` — one result verified and classified
   * - `done` — all results processed
   * - `error` — unrecoverable error
   *
   * @example
   * ```ts
   * for await (const event of client.searchStream("deep learning papers")) {
   *   if (event.event === "result") {
   *     console.log(event.data.scored_result);
   *   }
   * }
   * ```
   */
  async *searchStream(
    query: string,
    options?: {
      max_results?: number;
      verify?: boolean;
      decompose?: boolean;
      classify?: boolean;
      recency_filter?: string;
      adapters?: string[];
      timeout_seconds?: number;
    },
  ): AsyncGenerator<StreamEvent> {
    const response = await this.rawRequest("POST", "/v1/search", {
      query,
      options: {
        stream: true,
        ...options,
      },
    });

    if (!response.body) {
      throw new OpenSiftConnectionError("Response body is null — SSE streaming requires a readable stream");
    }

    yield* this.parseSSEStream(response.body);
  }

  // ── Batch search ─────────────────────────────────────────────────────────

  /**
   * Execute multiple search queries in a single batch request.
   *
   * @param queries - Array of natural language queries (max 20)
   * @param options - Shared search options for all queries
   * @returns Batch response with per-query results
   */
  async batchSearch(
    queries: string[],
    options?: {
      max_results?: number;
      verify?: boolean;
      decompose?: boolean;
      classify?: boolean;
      export_format?: "csv" | "json";
      recency_filter?: string;
      adapters?: string[];
      timeout_seconds?: number;
    },
  ): Promise<BatchSearchResponse> {
    const { export_format, ...searchOptions } = options ?? {};
    return this.post<BatchSearchResponse>("/v1/search/batch", {
      queries,
      options: searchOptions,
      ...(export_format ? { export_format } : {}),
    });
  }

  // ── Internal HTTP helpers ────────────────────────────────────────────────

  private async get<T>(path: string): Promise<T> {
    const response = await this.rawRequest("GET", path);
    return (await response.json()) as T;
  }

  private async post<T>(path: string, body: unknown): Promise<T> {
    const response = await this.rawRequest("POST", path, body);
    return (await response.json()) as T;
  }

  private async rawRequest(
    method: string,
    path: string,
    body?: unknown,
  ): Promise<Response> {
    const url = `${this.baseUrl}${path}`;
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), this.timeout);

    let response: Response;
    try {
      response = await this._fetch(url, {
        method,
        headers: this.headers,
        body: body !== undefined ? JSON.stringify(body) : undefined,
        signal: controller.signal,
      });
    } catch (error: unknown) {
      clearTimeout(timer);
      if (error instanceof DOMException && error.name === "AbortError") {
        throw new OpenSiftTimeoutError(this.timeout);
      }
      throw new OpenSiftConnectionError(
        `Failed to connect to ${url}: ${error instanceof Error ? error.message : String(error)}`,
        error instanceof Error ? error : undefined,
      );
    } finally {
      clearTimeout(timer);
    }

    if (!response.ok) {
      let body: unknown;
      try {
        body = await response.json();
      } catch {
        body = await response.text().catch(() => null);
      }
      if (response.status === 422) {
        throw new OpenSiftValidationError(body);
      }
      throw new OpenSiftAPIError(response.status, body);
    }

    return response;
  }

  // ── SSE parser ───────────────────────────────────────────────────────────

  private async *parseSSEStream(
    body: ReadableStream<Uint8Array>,
  ): AsyncGenerator<StreamEvent> {
    const reader = body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let currentEvent = "";
    const dataLines: string[] = [];

    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        // Keep incomplete last line in buffer
        buffer = lines.pop() ?? "";

        for (const line of lines) {
          if (line.startsWith("event:")) {
            currentEvent = line.slice(6).trim();
          } else if (line.startsWith("data:")) {
            dataLines.push(line.slice(5).trim());
          } else if (line === "" && currentEvent) {
            const rawData = dataLines.join("\n");
            let parsed: Record<string, unknown>;
            try {
              parsed = JSON.parse(rawData) as Record<string, unknown>;
            } catch {
              parsed = { raw: rawData };
            }
            yield {
              event: currentEvent as StreamEvent["event"],
              data: parsed,
            };
            currentEvent = "";
            dataLines.length = 0;
          }
        }
      }

      // Flush remaining event
      if (currentEvent && dataLines.length > 0) {
        const rawData = dataLines.join("\n");
        let parsed: Record<string, unknown>;
        try {
          parsed = JSON.parse(rawData) as Record<string, unknown>;
        } catch {
          parsed = { raw: rawData };
        }
        yield {
          event: currentEvent as StreamEvent["event"],
          data: parsed,
        };
      }
    } finally {
      reader.releaseLock();
    }
  }
}
