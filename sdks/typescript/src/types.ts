/**
 * TypeScript type definitions for the OpenSift API.
 *
 * These types mirror the Python Pydantic models in `src/opensift/models/`.
 */

// ── Request types ────────────────────────────────────────────────────────

export interface SearchOptions {
  decompose?: boolean;
  verify?: boolean;
  classify?: boolean;
  stream?: boolean;
  max_results?: number;
  recency_filter?: string | null;
  adapters?: string[] | null;
  timeout_seconds?: number;
}

export interface SearchContext {
  user_domain?: string | null;
  preferred_sources?: string[];
  excluded_sources?: string[];
  language?: string;
  extra?: Record<string, unknown>;
}

export interface SearchRequest {
  query: string;
  options?: SearchOptions;
  context?: SearchContext;
}

export interface BatchSearchRequest {
  queries: string[];
  options?: SearchOptions;
  context?: SearchContext;
  export_format?: "csv" | "json" | null;
}

// ── Criteria types ───────────────────────────────────────────────────────

export interface Criterion {
  criterion_id: string;
  type: string;
  name: string;
  description: string;
  weight: number;
}

export interface CriteriaResult {
  search_queries: string[];
  criteria: Criterion[];
}

// ── Assessment types ─────────────────────────────────────────────────────

export type AssessmentType =
  | "support"
  | "reject"
  | "somewhat_support"
  | "insufficient_information";

export interface Evidence {
  source: string;
  text: string;
}

export interface CriterionAssessment {
  criterion_id: string;
  assessment: AssessmentType;
  explanation: string;
  evidence: Evidence[];
}

export interface ValidationResult {
  criteria_assessment: CriterionAssessment[];
  summary: string;
}

export type ResultClassification = "perfect" | "partial" | "reject";

export interface ScoredResult {
  result: Record<string, unknown>;
  validation: ValidationResult;
  classification: ResultClassification;
  weighted_score: number;
}

export interface RawVerifiedResult {
  result: Record<string, unknown>;
  validation: ValidationResult;
}

// ── Response types ───────────────────────────────────────────────────────

export interface SearchResponse {
  request_id: string;
  status: string;
  processing_time_ms: number;
  query: string;
  criteria_result: CriteriaResult;
  perfect_results: ScoredResult[];
  partial_results: ScoredResult[];
  rejected_results: ScoredResult[];
  rejected_count: number;
  raw_results: RawVerifiedResult[];
  total_scanned: number;
}

export interface PlanResponse {
  request_id: string;
  query: string;
  criteria_result: CriteriaResult;
  processing_time_ms: number;
}

export interface BatchSearchResponse {
  status: string;
  processing_time_ms: number;
  total_queries: number;
  results: SearchResponse[];
  export_format?: string | null;
  export_data?: string | null;
}

// ── Streaming types ──────────────────────────────────────────────────────

export interface StreamEvent {
  event: "criteria" | "search_complete" | "result" | "done" | "error";
  data: Record<string, unknown>;
}

// ── Health types ─────────────────────────────────────────────────────────

export interface HealthResponse {
  status: string;
  version: string;
  service: string;
  default_adapter: string;
  active_adapters: string[];
}

export interface AdapterHealth {
  status: string;
  latency_ms?: number;
  error_rate?: number;
  message?: string;
}

export interface AdapterHealthResponse {
  adapters: Record<string, AdapterHealth>;
}

// ── Client configuration ─────────────────────────────────────────────────

export interface OpenSiftClientOptions {
  /** OpenSift server URL (e.g. "http://localhost:8080") */
  baseUrl: string;
  /** Request timeout in milliseconds. Default: 120000 (2 minutes) */
  timeout?: number;
  /** Custom headers to include in every request */
  headers?: Record<string, string>;
  /** Custom fetch implementation (for Node.js < 18 or testing) */
  fetch?: typeof globalThis.fetch;
}
