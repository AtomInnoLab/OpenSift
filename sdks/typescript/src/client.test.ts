import { describe, it, expect, vi, beforeEach } from "vitest";
import { OpenSiftClient } from "./client.js";
import {
  OpenSiftAPIError,
  OpenSiftValidationError,
  OpenSiftConnectionError,
  OpenSiftTimeoutError,
} from "./errors.js";
import type { HealthResponse, SearchResponse, PlanResponse, BatchSearchResponse } from "./types.js";

// ── Helpers ────────────────────────────────────────────────────────────────

function jsonResponse(data: unknown, status = 200): Response {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function sseResponse(events: Array<{ event: string; data: unknown }>): Response {
  const chunks = events.map(
    (e) => `event: ${e.event}\ndata: ${JSON.stringify(e.data)}\n\n`,
  );
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      const encoder = new TextEncoder();
      for (const chunk of chunks) {
        controller.enqueue(encoder.encode(chunk));
      }
      controller.close();
    },
  });
  return new Response(stream, {
    status: 200,
    headers: { "Content-Type": "text/event-stream" },
  });
}

// ── Fixtures ───────────────────────────────────────────────────────────────

const healthFixture: HealthResponse = {
  status: "healthy",
  version: "0.1.0",
  service: "opensift",
  default_adapter: "elasticsearch",
  active_adapters: ["elasticsearch", "wikipedia"],
};

const planFixture: PlanResponse = {
  request_id: "plan-123",
  query: "solar nowcasting deep learning",
  criteria_result: {
    search_queries: ["solar nowcasting deep learning", "photovoltaic forecasting neural network"],
    criteria: [
      {
        criterion_id: "criterion_1",
        type: "topic",
        name: "Solar nowcasting",
        description: "Paper must address solar energy nowcasting or short-term forecasting",
        weight: 0.5,
      },
      {
        criterion_id: "criterion_2",
        type: "method",
        name: "Deep learning",
        description: "Paper must use deep learning methods",
        weight: 0.5,
      },
    ],
  },
  processing_time_ms: 1234,
};

const searchFixture: SearchResponse = {
  request_id: "search-456",
  status: "completed",
  processing_time_ms: 5678,
  query: "solar nowcasting deep learning",
  criteria_result: planFixture.criteria_result,
  perfect_results: [
    {
      result: { title: "Deep Learning for Solar Nowcasting", source: "arxiv" },
      validation: {
        criteria_assessment: [
          {
            criterion_id: "criterion_1",
            assessment: "support",
            explanation: "Directly about solar nowcasting",
            evidence: [{ source: "title", text: "Deep Learning for Solar Nowcasting" }],
          },
        ],
        summary: "Highly relevant paper on solar nowcasting using deep learning.",
      },
      classification: "perfect",
      weighted_score: 0.95,
    },
  ],
  partial_results: [],
  rejected_results: [],
  rejected_count: 2,
  raw_results: [],
  total_scanned: 10,
};

const batchFixture: BatchSearchResponse = {
  status: "completed",
  processing_time_ms: 10000,
  total_queries: 2,
  results: [searchFixture, searchFixture],
};

// ── Tests ──────────────────────────────────────────────────────────────────

describe("OpenSiftClient", () => {
  let mockFetch: ReturnType<typeof vi.fn>;
  let client: OpenSiftClient;

  beforeEach(() => {
    mockFetch = vi.fn();
    client = new OpenSiftClient({
      baseUrl: "http://localhost:8080",
      fetch: mockFetch,
    });
  });

  // ── Health ──

  describe("health()", () => {
    it("returns server health status", async () => {
      mockFetch.mockResolvedValueOnce(jsonResponse(healthFixture));

      const result = await client.health();

      expect(result).toEqual(healthFixture);
      expect(mockFetch).toHaveBeenCalledWith(
        "http://localhost:8080/v1/health",
        expect.objectContaining({ method: "GET" }),
      );
    });
  });

  describe("adapterHealth()", () => {
    it("returns per-adapter health", async () => {
      const fixture = {
        adapters: {
          elasticsearch: { status: "healthy", latency_ms: 12 },
        },
      };
      mockFetch.mockResolvedValueOnce(jsonResponse(fixture));

      const result = await client.adapterHealth();

      expect(result.adapters.elasticsearch?.status).toBe("healthy");
    });
  });

  // ── Plan ──

  describe("plan()", () => {
    it("generates search plan from query", async () => {
      mockFetch.mockResolvedValueOnce(jsonResponse(planFixture));

      const result = await client.plan("solar nowcasting deep learning");

      expect(result.request_id).toBe("plan-123");
      expect(result.criteria_result.search_queries).toHaveLength(2);
      expect(result.criteria_result.criteria).toHaveLength(2);

      const body = JSON.parse(mockFetch.mock.calls[0][1].body);
      expect(body.query).toBe("solar nowcasting deep learning");
      expect(body.options.decompose).toBe(true);
    });

    it("respects decompose=false option", async () => {
      mockFetch.mockResolvedValueOnce(jsonResponse(planFixture));

      await client.plan("test query", { decompose: false });

      const body = JSON.parse(mockFetch.mock.calls[0][1].body);
      expect(body.options.decompose).toBe(false);
    });
  });

  // ── Search (complete) ──

  describe("search()", () => {
    it("returns complete search response", async () => {
      mockFetch.mockResolvedValueOnce(jsonResponse(searchFixture));

      const result = await client.search("solar nowcasting deep learning");

      expect(result.request_id).toBe("search-456");
      expect(result.perfect_results).toHaveLength(1);
      expect(result.perfect_results[0]?.classification).toBe("perfect");
      expect(result.rejected_count).toBe(2);
    });

    it("sends correct options", async () => {
      mockFetch.mockResolvedValueOnce(jsonResponse(searchFixture));

      await client.search("test", {
        max_results: 5,
        verify: false,
        decompose: true,
        classify: false,
      });

      const body = JSON.parse(mockFetch.mock.calls[0][1].body);
      expect(body.options.stream).toBe(false);
      expect(body.options.max_results).toBe(5);
      expect(body.options.verify).toBe(false);
      expect(body.options.classify).toBe(false);
    });
  });

  // ── Search (streaming) ──

  describe("searchStream()", () => {
    it("yields SSE events from stream", async () => {
      const sseEvents = [
        {
          event: "criteria",
          data: { request_id: "s-1", criteria_result: planFixture.criteria_result },
        },
        {
          event: "result",
          data: { index: 0, total: 1, scored_result: searchFixture.perfect_results[0] },
        },
        {
          event: "done",
          data: { perfect_count: 1, partial_count: 0, rejected_count: 0, processing_time_ms: 1000 },
        },
      ];
      mockFetch.mockResolvedValueOnce(sseResponse(sseEvents));

      const collected: Array<{ event: string; data: Record<string, unknown> }> = [];
      for await (const event of client.searchStream("test query")) {
        collected.push(event);
      }

      expect(collected).toHaveLength(3);
      expect(collected[0]?.event).toBe("criteria");
      expect(collected[1]?.event).toBe("result");
      expect(collected[2]?.event).toBe("done");
    });

    it("sends stream=true in options", async () => {
      mockFetch.mockResolvedValueOnce(sseResponse([]));

      const events: unknown[] = [];
      for await (const event of client.searchStream("test")) {
        events.push(event);
      }

      const body = JSON.parse(mockFetch.mock.calls[0][1].body);
      expect(body.options.stream).toBe(true);
    });
  });

  // ── Batch search ──

  describe("batchSearch()", () => {
    it("sends multiple queries and returns batch response", async () => {
      mockFetch.mockResolvedValueOnce(jsonResponse(batchFixture));

      const result = await client.batchSearch(["query1", "query2"], {
        max_results: 5,
      });

      expect(result.total_queries).toBe(2);
      expect(result.results).toHaveLength(2);

      const body = JSON.parse(mockFetch.mock.calls[0][1].body);
      expect(body.queries).toEqual(["query1", "query2"]);
      expect(body.options.max_results).toBe(5);
    });

    it("includes export_format when specified", async () => {
      mockFetch.mockResolvedValueOnce(jsonResponse(batchFixture));

      await client.batchSearch(["q1"], { export_format: "csv" });

      const body = JSON.parse(mockFetch.mock.calls[0][1].body);
      expect(body.export_format).toBe("csv");
    });
  });

  // ── Error handling ──

  describe("error handling", () => {
    it("throws OpenSiftValidationError on 422", async () => {
      const errorBody = { detail: [{ msg: "field required", loc: ["body", "query"] }] };
      mockFetch.mockResolvedValueOnce(
        new Response(JSON.stringify(errorBody), { status: 422 }),
      );

      await expect(client.search("")).rejects.toThrow(OpenSiftValidationError);
    });

    it("throws OpenSiftAPIError on 500", async () => {
      mockFetch.mockResolvedValueOnce(
        new Response(JSON.stringify({ detail: "Internal error" }), { status: 500 }),
      );

      await expect(client.search("test")).rejects.toThrow(OpenSiftAPIError);
      try {
        await client.search("test");
      } catch (e) {
        // Already thrown above
      }
    });

    it("throws OpenSiftConnectionError on network failure", async () => {
      mockFetch.mockRejectedValueOnce(new TypeError("fetch failed"));

      await expect(client.health()).rejects.toThrow(OpenSiftConnectionError);
    });

    it("throws OpenSiftTimeoutError on abort", async () => {
      mockFetch.mockRejectedValueOnce(
        Object.assign(new DOMException("signal is aborted", "AbortError")),
      );

      await expect(client.health()).rejects.toThrow(OpenSiftTimeoutError);
    });
  });

  // ── Configuration ──

  describe("configuration", () => {
    it("strips trailing slash from baseUrl", async () => {
      const c = new OpenSiftClient({
        baseUrl: "http://localhost:8080///",
        fetch: mockFetch,
      });
      mockFetch.mockResolvedValueOnce(jsonResponse(healthFixture));

      await c.health();

      expect(mockFetch).toHaveBeenCalledWith(
        "http://localhost:8080/v1/health",
        expect.anything(),
      );
    });

    it("merges custom headers", async () => {
      const c = new OpenSiftClient({
        baseUrl: "http://localhost:8080",
        headers: { Authorization: "Bearer token123" },
        fetch: mockFetch,
      });
      mockFetch.mockResolvedValueOnce(jsonResponse(healthFixture));

      await c.health();

      const headers = mockFetch.mock.calls[0][1].headers;
      expect(headers["Authorization"]).toBe("Bearer token123");
      expect(headers["Content-Type"]).toBe("application/json");
    });
  });
});
