# OpenSift Docker Image
# Multi-stage build for optimized image size

# ─── Stage 1: Build ─────────────────────────────────────
FROM python:3.13-slim AS builder

WORKDIR /build

# Install build dependencies
RUN pip install --no-cache-dir poetry>=2.0

# Copy dependency files first (for cache efficiency)
COPY pyproject.toml poetry.lock* ./

# Export requirements (without dev dependencies)
RUN poetry export -f requirements.txt --without=dev --output requirements.txt 2>/dev/null || \
    poetry install --no-interaction --no-root --without=dev

# ─── Stage 2: Runtime ───────────────────────────────────
FROM python:3.13-slim AS runtime

WORKDIR /app

# Install runtime system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -r opensift && useradd -r -g opensift -d /app opensift

# Copy requirements and install
COPY --from=builder /build/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt 2>/dev/null || true

# Copy application source
COPY src/ ./src/
COPY pyproject.toml ./

# Install the package
RUN pip install --no-cache-dir .

# Switch to non-root user
USER opensift

# Expose port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:8080/v1/health || exit 1

# Default command
ENTRYPOINT ["opensift"]
CMD ["--host", "0.0.0.0", "--port", "8080"]
