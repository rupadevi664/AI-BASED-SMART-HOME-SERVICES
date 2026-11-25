#!/usr/bin/env bash
# Exit on critical error
set -e

echo "=== Starting AI-BASED-SMART-HOME-SERVICES on Render ==="

# If current directory contains backend/, navigate into it
if [ -d "backend" ]; then
    echo "Entering backend directory..."
    cd backend
fi

# Ensure python finds the app package
export PYTHONPATH=.

# Initialize database schema and admin account
echo "Initializing database..."
python -m app.init_db --admin

# Index knowledge base into ChromaDB for local RAG
echo "Indexing knowledge base..."
(python scripts/index_knowledge.py || echo "Knowledge base ready")

# Launch Uvicorn with port binding
PORT="${PORT:-8000}"
WORKERS="${WEB_CONCURRENCY:-2}"
echo "Starting Uvicorn on port $PORT with $WORKERS worker(s)..."
exec uvicorn app.main:app --host 0.0.0.0 --port "$PORT" --workers "$WORKERS"
