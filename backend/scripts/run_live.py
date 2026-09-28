"""Launch the API for local development.

Reads DATABASE_URL from the environment / backend/.env (MySQL in this setup).

Usage (from backend/):
    .venv\\Scripts\\python scripts\\run_live.py
"""
import os
import sys

# Make `app` importable regardless of how the script is invoked.
BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

import uvicorn  # noqa: E402  (late import is intentional in this launcher)

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000)
