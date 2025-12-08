# HAIA Production Dockerfile
# Multi-stage build for optimized image size

# Build stage: Install dependencies
FROM python:3.11-slim as builder

WORKDIR /build

# Install uv for dependency management
RUN pip install --no-cache-dir uv

# Copy dependency files and README (needed for package build)
COPY pyproject.toml uv.lock* README.md ./

# Copy source code (needed for editable install)
COPY src/ ./src/

# Install dependencies to /build/.venv
RUN uv sync --frozen --no-dev

# Production stage: Minimal runtime image
FROM python:3.11-slim

WORKDIR /app

# Install runtime dependencies only
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder
COPY --from=builder /build/.venv /app/.venv

# Copy application code and package metadata
COPY src/ /app/src/
COPY pyproject.toml README.md /app/

# Set environment variables
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app/src

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Expose API port
EXPOSE 8000

# Run HAIA API server
CMD ["python", "-m", "haia.main"]
