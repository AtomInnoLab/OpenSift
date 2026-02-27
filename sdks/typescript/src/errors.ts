/**
 * Custom error types for the OpenSift client.
 */

export class OpenSiftError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "OpenSiftError";
  }
}

export class OpenSiftAPIError extends OpenSiftError {
  readonly status: number;
  readonly body: unknown;

  constructor(status: number, body: unknown, message?: string) {
    const msg =
      message ?? `OpenSift API error (HTTP ${status}): ${formatBody(body)}`;
    super(msg);
    this.name = "OpenSiftAPIError";
    this.status = status;
    this.body = body;
  }
}

export class OpenSiftValidationError extends OpenSiftAPIError {
  constructor(body: unknown) {
    super(422, body, `OpenSift validation error: ${formatBody(body)}`);
    this.name = "OpenSiftValidationError";
  }
}

export class OpenSiftTimeoutError extends OpenSiftError {
  constructor(timeoutMs: number) {
    super(`OpenSift request timed out after ${timeoutMs}ms`);
    this.name = "OpenSiftTimeoutError";
  }
}

export class OpenSiftConnectionError extends OpenSiftError {
  readonly cause?: Error;

  constructor(message: string, cause?: Error) {
    super(message);
    this.name = "OpenSiftConnectionError";
    this.cause = cause;
  }
}

function formatBody(body: unknown): string {
  if (typeof body === "string") return body;
  try {
    return JSON.stringify(body);
  } catch {
    return String(body);
  }
}
