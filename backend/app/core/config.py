"""Application configuration loaded from environment / .env file.

Never hard-code credentials; everything comes from here.
"""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent.parent  # backend/


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Database ---
    # mysql+pymysql://user:password@host:3306/dbname   (production)
    # sqlite:///:memory:                               (tests, set via env)
    DATABASE_URL: str = "sqlite:///./ai_home_services.db"

    # --- JWT ---
    JWT_SECRET_KEY: str = "CHANGE_THIS_SECRET"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # --- Optional initial admin seeding (python -m app.init_db --admin) ---
    ADMIN_EMAIL: str = "admin@example.com"
    ADMIN_PASSWORD: str = "CHANGE_THIS_ADMIN_PASSWORD"
    ADMIN_NAME: str = "Platform Admin"

    # --- Phase 5: live location tracking ---
    # Minimum seconds between ACCEPTED location updates per booking
    # (anti-flood throttle; not a GPS sampling rate).
    LOCATION_UPDATE_INTERVAL_SECONDS: float = 1.0
    # Retention window for live_locations (informational; cleanup is an
    # explicit, opt-in maintenance action — never a silent background task).
    LOCATION_HISTORY_RETENTION_DAYS: int = 7

    # Comma-separated frontend origins allowed by CORS (React/Vite dev server
    # by default). Never "*" in production.
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"

    # --- Phase 6: Razorpay payments ---
    # Get test-mode keys from the Razorpay dashboard (Settings → API Keys).
    # KEY_ID is public (sent to the frontend for Checkout); KEY_SECRET must
    # never leave the backend — it is used to verify payment signatures.
    # Leave both empty to run without payments (endpoints respond 503).
    RAZORPAY_KEY_ID: str = ""
    RAZORPAY_KEY_SECRET: str = ""
    # Currency for created orders (Razorpay supports INR primarily).
    RAZORPAY_CURRENCY: str = "INR"

    # --- Phase 7: Google Gemini (AI assistant) ---
    # Get a key from Google AI Studio (https://aistudio.google.com/apikey).
    # The key NEVER leaves the backend; the React app only talks to /llm/chat.
    # Leave empty to run without the assistant (POST /llm/chat responds 503
    # LLM_NOT_CONFIGURED), mirroring the payments gate.
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.0-flash"
    # Per-request timeout for the Gemini REST call (seconds).
    GEMINI_TIMEOUT_SECONDS: float = 20.0
    # Maximum conversation turns the client may send as history (last N kept).
    GEMINI_MAX_HISTORY_TURNS: int = 8

    # --- Phase 8: RAG (retrieval-augmented generation) ---
    # Knowledge base + ChromaDB paths (relative to backend/).
    RAG_KB_DIR: str = "knowledge_base"
    RAG_CHROMA_DIR: str = "chroma_data"
    RAG_COLLECTION_NAME: str = "home_services_kb"
    # Chunking: markdown sections split on "## " headings; oversized sections
    # are windowed with overlap. In characters (local MiniLM handles this well).
    RAG_CHUNK_SIZE: int = 800
    RAG_CHUNK_OVERLAP: int = 100
    # Retrieval: candidates fetched per query and the cosine-distance relevance
    # threshold (0 = identical, 2 = opposite). Calibrated on the demo queries:
    # relevant chunks score ~0.24-0.67, unrelated questions ~0.94+ → 0.85 sits
    # in the gap with margin on both sides.
    RAG_TOP_K: int = 3
    RAG_MAX_DISTANCE: float = 0.85
    # Local ONNX all-MiniLM-L6-v2 (384-dim, bundled with ChromaDB) — no API key.
    # Swap to a Google embedding model here if ever desired.
    RAG_EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
