# ==============================================================================
# Guardian Hub — Portable Containerized AI System
# ==============================================================================
# Decouples Guardian from local Windows hardware into a portable Linux container.
# All state (SQLite databases, ChromaDB, cryptographic audit logs) resides in
# mounted persistent volumes, never baked into the container image.
# ==============================================================================

FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    GUARDIAN_DATA_DIR=/app/.guardian

WORKDIR /app

# Install minimal OS dependencies for compilation and networking
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    git \
    curl \
    sqlite3 \
    libasound2 \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies using cross-platform Linux specifications
COPY requirements-docker.txt /app/
RUN pip install --upgrade pip setuptools wheel && \
    pip install -r requirements-docker.txt

# Copy source tree and configuration
COPY pyproject.toml /app/
COPY guardian /app/guardian
COPY tests /app/tests
COPY docs /app/docs
COPY scripts /app/scripts
COPY GUARDIAN_CONSTITUTION_v0.1.md /app/

# Install guardian in editable mode without reinstalling dependencies
RUN pip install -e . --no-deps

# Create directories for persistent volumes
RUN mkdir -p /app/data /app/memory /app/.guardian /app/logs

# Hardening: Create unprivileged user
RUN useradd -m -u 1000 guardian && \
    chown -R guardian:guardian /app

USER guardian

EXPOSE 8000

# Health check against unauthenticated /api/health endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://127.0.0.1:8000/api/health || exit 1

CMD ["python", "-m", "guardian", "gateway", "start"]
