# ==============================================================================
# Production Dockerfile for FastAPI Backend
# Multi-arch ready, non-root user, lightweight Debian slim base
# ==============================================================================
FROM python:3.11-slim

# Prevent python from generating .pyc and enable real-time unbuffered logging
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/backend \
    PORT=8000 \
    HOST=0.0.0.0

WORKDIR /app

# Install minimal OS build tools and curl for healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies in isolated layer for fast build caching
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r /app/backend/requirements.txt

# Copy knowledge base documentation for local RAG embeddings
COPY knowledge_base /app/knowledge_base

# Copy backend application source code
COPY backend /app/backend

# Ensure shell scripts have Unix line endings and executable flags
WORKDIR /app/backend
RUN chmod +x /app/backend/entrypoint.sh && \
    mkdir -p /app/backend/chroma_data && \
    useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app

# Run container as unprivileged user
USER appuser

EXPOSE 8000

# Docker healthcheck pinging the /health endpoint
HEALTHCHECK --interval=20s --timeout=5s --start-period=15s --retries=3 \
  CMD curl -f http://127.0.0.1:8000/health || exit 1

ENTRYPOINT ["/app/backend/entrypoint.sh"]
