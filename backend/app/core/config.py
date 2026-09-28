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


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
