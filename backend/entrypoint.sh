#!/bin/sh
set -e

echo "=========================================================="
echo " Starting AI-BASED-SMART-HOME-SERVICES Backend Production"
echo "=========================================================="

# 1. Wait for database connection if external database is configured
if [ -n "$DATABASE_URL" ]; then
    echo "Probing database connectivity..."
    python - <<'EOF'
import os
import sys
import time
from sqlalchemy import create_engine, select

url = os.getenv("DATABASE_URL", "")
if url and not url.startswith("sqlite"):
    max_retries = 30
    retry_interval = 2
    for attempt in range(1, max_retries + 1):
        try:
            engine = create_engine(url, pool_pre_ping=True)
            with engine.connect() as conn:
                conn.execute(select(1))
            print(f"Database reachable on attempt {attempt}/{max_retries}.")
            sys.exit(0)
        except Exception as e:
            print(f"Attempt {attempt}/{max_retries}: Database unavailable ({e.__class__.__name__}). Retrying in {retry_interval}s...")
            time.sleep(retry_interval)
    print("Error: Could not reach database within timeout.")
    sys.exit(1)
EOF
fi

# 2. Run database initialization and ensure admin account exists
echo "Checking and executing database initialization..."
python -m app.init_db --admin || echo "Database initialization completed with warnings."

# 3. Index knowledge-base documents into ChromaDB for RAG if present
if [ -d "../knowledge_base" ] || [ -d "knowledge_base" ]; then
    echo "Verifying local RAG knowledge base embeddings..."
    python scripts/index_knowledge.py || echo "Knowledge base indexing finished."
fi

# 4. Launch Uvicorn with production concurrency and proxy header awareness
WORKERS=${WEB_CONCURRENCY:-2}
PORT=${PORT:-8000}
HOST=${HOST:-0.0.0.0}

echo "Launching Uvicorn server on ${HOST}:${PORT} (${WORKERS} worker process(es))..."
exec uvicorn app.main:app --host "$HOST" --port "$PORT" --workers "$WORKERS" --proxy-headers --forwarded-allow-ips='*'
